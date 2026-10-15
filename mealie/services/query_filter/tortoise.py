"""Tortoise implementation of Mealie's existing query-filter language.

The legacy model graph remains the source of the public filterability policy
while both ORM paths coexist. The Tortoise models are resolved by table and
field names; this bridge can be removed with the legacy models at Stage 18.
"""

from __future__ import annotations

from copy import copy
from typing import Any

from dateutil import parser as date_parser
from dateutil.parser import ParserError
from pypika_tortoise.functions import Lower
from pypika_tortoise.terms import ValueWrapper
from sqlalchemy.sql import sqltypes
from tortoise import Model
from tortoise.expressions import Q, Subquery
from tortoise.filters import Like

from mealie.db.models import _all_models as _legacy_models  # noqa: F401
from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._model_utils.datetime import NaiveDateTime
from mealie.db.models._model_utils.guid import GUID
from mealie.services.query_filter.builder import (
    QueryFilterBuilder,
    QueryFilterBuilderComponent,
)
from mealie.services.query_filter.keywords import RelationalKeyword
from mealie.services.query_filter.operators import LogicalOperator, RelationalOperator

_OPERATOR_SUFFIX: dict[Any, str] = {
    RelationalOperator.EQ: "",
    RelationalOperator.NOTEQ: "not",
    RelationalOperator.GT: "gt",
    RelationalOperator.LT: "lt",
    RelationalOperator.GTE: "gte",
    RelationalOperator.LTE: "lte",
    RelationalKeyword.IN: "in",
    RelationalKeyword.NOT_IN: "not_in",
    RelationalKeyword.IS: "isnull",
    RelationalKeyword.IS_NOT: "isnull",
    RelationalKeyword.LIKE: "iregex",
    RelationalKeyword.NOT_LIKE: "iregex",
}


def _legacy_model_for_table(table: str) -> type[SqlAlchemyBase]:
    for mapper in SqlAlchemyBase.registry.mappers:
        if mapper.local_table.name == table:
            return mapper.class_
    raise ValueError(f"No legacy filter policy is registered for table '{table}'")


def _legacy_field_path(model: type[Model], dotted_path: str) -> tuple[Any, list[bool]]:
    legacy_model = _legacy_model_for_table(model._meta.db_table)
    relationships: list[tuple[Any, bool]] = []
    _target, legacy_attr = QueryFilterBuilder.get_model_and_model_attr_from_attr_string(
        dotted_path, legacy_model, collect_relationships=relationships
    )
    # Ensure the final scalar exists in the Tortoise graph too. Association
    # proxies are resolved by the legacy builder; their public path is retained
    # as a filter path only when the Tortoise graph exposes that same path.
    current = model
    tortoise_path = dotted_path
    if model._meta.db_table == "recipes":
        tortoise_path = tortoise_path.replace("recipe_ingredient", "ingredients")
        if tortoise_path == "household_id":
            tortoise_path = "user.household_id"
    tortoise_parts = tortoise_path.split(".")
    for index, part in enumerate(tortoise_parts):
        field = current._meta.fields_map.get(part)
        if field is None:
            raise ValueError(f"invalid attribute string: '{dotted_path}' does not exist on this schema")
        if index != len(tortoise_parts) - 1:
            related = getattr(field, "related_model", None)
            if related is None:
                raise ValueError(f"invalid attribute string: '{dotted_path}' does not exist on this schema")
            current = related
    return legacy_attr, [is_collection for _, is_collection in relationships]


def _validated_value(component: QueryFilterBuilderComponent, legacy_attr: Any) -> Any:
    """Apply the same scalar conversion rules used by the SQLAlchemy builder."""
    value = component.value
    values = value if isinstance(value, list) else [value]
    field_type = legacy_attr.type
    if component.relationship in (RelationalKeyword.LIKE, RelationalKeyword.NOT_LIKE) and not isinstance(
        field_type, sqltypes.String
    ):
        raise ValueError(f'invalid query string: "{component.relationship.value}" can only be used with string columns')
    result: list[Any] = []
    for item in values:
        if item is None:
            result.append(None)
        elif isinstance(field_type, sqltypes.String):
            result.append(str(item).lower())
        elif isinstance(field_type, GUID):
            from uuid import UUID

            try:
                UUID(str(item))
            except ValueError as error:
                raise ValueError(f"invalid query string: invalid UUID '{item}'") from error
            result.append(item)
        elif isinstance(field_type, sqltypes.Date | sqltypes.DateTime | NaiveDateTime):
            try:
                parsed = date_parser.parse(str(item))
            except ParserError as error:
                raise ValueError(f"invalid query string: unknown date or datetime format '{item}'") from error
            result.append(parsed.date() if isinstance(field_type, sqltypes.Date) else parsed)
        elif isinstance(field_type, sqltypes.Boolean):
            if not str(item):
                raise ValueError("invalid query string")
            result.append(str(item).lower()[0] in ("t", "y") or item == "1")
        else:
            result.append(item)
    return result if isinstance(value, list) else result[0]


def _case_insensitive_key(path: str, legacy_attr: Any, suffix: str) -> str:
    if not isinstance(legacy_attr.type, sqltypes.String):
        return f"{path}__{suffix}" if suffix else path
    if suffix in ("in", "not_in"):
        return f"{path}__{suffix}"
    if suffix == "iregex":
        return f"{path}__{suffix}"
    if suffix == "isnull":
        return f"{path}__isnull"
    return f"{path}__i{suffix}" if suffix else f"{path}__iexact"


def _string_membership(path: str, values: list[Any], *, negate: bool, model: type[Model]) -> Q:
    if not values:
        return Q() if negate else Q(**{f"{model._meta.pk_attr}__in": []})
    result = Q(**{f"{path}__iexact": values[0]})
    for item in values[1:]:
        result |= Q(**{f"{path}__iexact": item})
    return ~result if negate else result


def _register_legacy_like(model: type[Model], dotted_path: str) -> str:
    """Register a bound-parameter LIKE filter on the path's terminal model."""
    current = model
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        current = current._meta.fields_map[part].related_model
    field_name = parts[-1]
    filter_key = f"{field_name}__stage7_like"
    if filter_key not in current._meta.filters:
        template = current._meta.filters.get(f"{field_name}__iexact")
        if template is None:
            template = current._meta.filters[field_name]

        def insensitive_like(field, value):
            return Like(Lower(field), ValueWrapper(str(value).lower()))

        custom = copy(template)
        custom["field"] = field_name
        custom["source_field"] = current._meta.fields_map[field_name].source_field or field_name
        custom["operator"] = insensitive_like
        custom["value_encoder"] = lambda value, _model, _field: value
        current._meta.filters[filter_key] = custom
    return f"{dotted_path.replace('.', '__')}__stage7_like"


class TortoiseFilterCompiler:
    """Compile query-filter expressions to Tortoise Q trees."""

    @classmethod
    def compile(cls, expression: str, model: type[Model]) -> Q:  # noqa: C901
        builder = QueryFilterBuilder(expression)
        parts = builder.filter_components
        index = 0

        def atom() -> Q:  # noqa: C901
            nonlocal index
            if index >= len(parts):
                raise ValueError("invalid query string")
            part = parts[index]
            if part == "(":
                index += 1
                nested = or_group()
                if index >= len(parts) or parts[index] != ")":
                    raise ValueError("invalid query string: parenthesis are unbalanced")
                index += 1
                return nested
            if not isinstance(part, QueryFilterBuilderComponent):
                raise ValueError("invalid query string")
            index += 1
            legacy_attr, relationships = _legacy_field_path(model, part.attribute_name)
            value = _validated_value(part, legacy_attr)
            resolved_path = part.attribute_name
            if model._meta.db_table == "recipes":
                resolved_path = resolved_path.replace("recipe_ingredient", "ingredients")
                if resolved_path == "household_id":
                    resolved_path = "user.household_id"
            path = resolved_path.replace(".", "__")
            operator = part.relationship

            def related_ids(filter_q: Q) -> Subquery:
                matching = model.filter(filter_q).distinct().values_list(model._meta.pk_attr, flat=True)
                return Subquery(matching)

            if operator is RelationalKeyword.CONTAINS_ALL:
                if not isinstance(value, list):
                    raise ValueError(
                        "invalid query string: CONTAINS ALL must be given a list of values enclosed by [ and ]"
                    )
                if not relationships:
                    if isinstance(legacy_attr.type, sqltypes.String):
                        return _string_membership(path, value, negate=False, model=model)
                    return Q(**{f"{path}__in": value})
                if not value:
                    return Q()
                primary_key = model._meta.pk_attr
                conditions = []
                for required_value in value:
                    key = _case_insensitive_key(path, legacy_attr, "exact")
                    conditions.append(Q(**{f"{primary_key}__in": related_ids(Q(**{key: required_value}))}))
                result = conditions[0]
                for condition in conditions[1:]:
                    result &= condition
                return result

            if operator in (RelationalKeyword.IS, RelationalKeyword.IS_NOT):
                key = f"{path}__isnull"
                match = operator is RelationalKeyword.IS
                if relationships:
                    return Q(**{f"{model._meta.pk_attr}__in": related_ids(Q(**{key: match}))})
                return Q(**{key: match})
            suffix = _OPERATOR_SUFFIX.get(operator)
            if suffix is None:
                raise ValueError(f"invalid relationship {operator}")
            if operator in (RelationalKeyword.LIKE, RelationalKeyword.NOT_LIKE):
                like_path = _register_legacy_like(model, resolved_path)
                q = Q(**{like_path: value})
                if operator is RelationalKeyword.NOT_LIKE:
                    q = ~q & Q(**{f"{path}__not_isnull": True})
                if relationships:
                    matching = model.filter(q).distinct().values_list(model._meta.pk_attr, flat=True)
                    return Q(**{f"{model._meta.pk_attr}__in": Subquery(matching)})
                return q
            key = _case_insensitive_key(path, legacy_attr, suffix)
            if isinstance(legacy_attr.type, sqltypes.String) and operator in (
                RelationalKeyword.IN,
                RelationalKeyword.NOT_IN,
            ):
                values = value if isinstance(value, list) else [value]
                match_q = _string_membership(path, values, negate=operator is RelationalKeyword.NOT_IN, model=model)
            elif isinstance(legacy_attr.type, sqltypes.String) and operator is RelationalOperator.NOTEQ:
                match_q = ~Q(**{f"{path}__iexact": value})
            else:
                match_q = Q(**{key: value})
            if operator is RelationalOperator.NOTEQ:
                match_q &= Q(**{f"{path}__not_isnull": True})
            if relationships:
                if operator is RelationalKeyword.NOT_IN:
                    positive_key = _case_insensitive_key(path, legacy_attr, "in")
                    if isinstance(legacy_attr.type, sqltypes.String):
                        positive_q = _string_membership(path, value, negate=False, model=model)
                    else:
                        positive_q = Q(**{positive_key: value})
                    return Q(**{f"{model._meta.pk_attr}__not_in": related_ids(positive_q)})
                matching = model.filter(match_q).distinct().values_list(model._meta.pk_attr, flat=True)
                return Q(**{f"{model._meta.pk_attr}__in": Subquery(matching)})
            if operator is RelationalKeyword.NOT_IN and not relationships and value:
                match_q &= Q(**{f"{path}__not_isnull": True})
            return match_q

        def and_group() -> Q:
            nonlocal index
            result = atom()
            while index < len(parts) and parts[index] is LogicalOperator.AND:
                index += 1
                result &= atom()
            return result

        def or_group() -> Q:
            nonlocal index
            result = and_group()
            while index < len(parts) and parts[index] is LogicalOperator.OR:
                index += 1
                result |= and_group()
            return result

        if not parts:
            return Q()
        compiled = or_group()
        if index != len(parts):
            raise ValueError("invalid query string")
        return compiled


def is_related_path(model: type[Model], dotted_path: str) -> bool:
    """Validate filterability and report whether a path crosses a relation."""
    _, relationships = _legacy_field_path(model, dotted_path)
    return bool(relationships)


def validate_order_path(model: type[Model], dotted_path: str) -> tuple[str, bool, bool]:
    """Return Tortoise path, whether it is related, and whether it is to-many."""
    _, relationships = _legacy_field_path(model, dotted_path)
    if model._meta.db_table == "recipes":
        dotted_path = dotted_path.replace("recipe_ingredient", "ingredients")
        if dotted_path == "household_id":
            dotted_path = "user.household_id"
    current = model
    for index, part in enumerate(dotted_path.split(".")):
        field = current._meta.fields_map[part]
        if index < len(dotted_path.split(".")) - 1:
            current = field.related_model
    return dotted_path.replace(".", "__"), bool(relationships), any(relationships)
