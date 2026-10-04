"""Applies Mealie's query filter language to Tortoise querysets.

Parsing is shared with QueryFilterBuilder; only the part that turns parsed components into
database conditions is reimplemented. The semantics follow the SQLAlchemy version:

* only columns marked filterable can be used (FILTERABLE),
* string comparisons ignore case,
* conditions on related rows are "some related row matches" (EXISTS), written here as
  ``id IN (subquery)`` so the outer rows are never duplicated by a join,
* NOT IN over a relationship means "no related row matches",
* CONTAINS ALL needs a separate matching related row for each value,
* groups combine from the right: ``a AND b OR c`` is ``a AND (b OR c)``.
"""

from __future__ import annotations

import datetime
import uuid
from collections import deque
from typing import Any

from dateutil import parser as date_parser
from dateutil.parser import ParserError
from humps import decamelize
from tortoise import fields as tfields
from tortoise.expressions import Q, Subquery
from tortoise.functions import Max, Min
from tortoise.models import Model
from tortoise.queryset import QuerySet

from mealie.db.tortoise.fields import GUIDField
from mealie.db.tortoise.models import FILTERABLE, PROXIES

from .builder import NonFilterableValueError, QueryFilterBuilder, QueryFilterBuilderComponent
from .keywords import RelationalKeyword
from .operators import LogicalOperator, RelationalOperator


class ResolvedAttribute:
    def __init__(self, path: str, field: tfields.Field, through_relation: bool) -> None:
        self.path = path
        self.field = field
        self.through_relation = through_relation

    @property
    def is_string(self) -> bool:
        return isinstance(self.field, tfields.CharField | tfields.TextField)


def resolve_attribute(model: type[Model], attr_string: str) -> ResolvedAttribute:
    """Turns "recipeCategory.name" into the Tortoise path "recipe_category__name"."""
    chain = decamelize(attr_string).split(".")
    if not chain or not chain[0]:
        raise ValueError("invalid query string: attribute name cannot be empty")

    current = model
    parts: list[str] = []
    for i, link in enumerate(chain):
        proxy = PROXIES.get(current.__name__, {}).get(link)
        if proxy:
            relation, link = proxy.split("__")
            parts.append(relation)
            current = current._meta.fields_map[relation].related_model

        if i == len(chain) - 1:
            if link == "updated_at":
                link = "update_at"  # synonym in the SQLAlchemy models
            field = current._meta.fields_map.get(link)
            if field is None or link in current._meta.fetch_fields:
                raise ValueError(f"invalid attribute string: '{attr_string}' does not exist on this schema")
            if link not in FILTERABLE.get(current.__name__, []):
                raise NonFilterableValueError(link)  # type: ignore[arg-type]
            parts.append(link)
            return ResolvedAttribute("__".join(parts), field, through_relation=len(parts) > 1)

        relation_field = current._meta.fields_map.get(link)
        if relation_field is None or link not in current._meta.fetch_fields:
            raise ValueError(f"invalid attribute string: '{attr_string}' does not exist on this schema")
        parts.append(link)
        current = relation_field.related_model

    raise ValueError(f"invalid attribute string: '{attr_string}'")


def _validate(component: QueryFilterBuilderComponent, attr: ResolvedAttribute) -> Any:
    values: list[Any] = list(component.value) if isinstance(component.value, list) else [component.value]
    field = attr.field
    for i, v in enumerate(values):
        if v is None:
            continue
        if attr.is_string:
            values[i] = v.lower()
        if component.relationship in (RelationalKeyword.LIKE, RelationalKeyword.NOT_LIKE) and not attr.is_string:
            raise ValueError(
                f'invalid query string: "{component.relationship.value}" can only be used with string columns'
            )
        if isinstance(field, GUIDField):
            try:
                values[i] = uuid.UUID(v)
            except ValueError as e:
                raise ValueError(f"invalid query string: invalid UUID '{v}'") from e
        if isinstance(field, tfields.DateField | tfields.DatetimeField):
            try:
                dt = date_parser.parse(v)
            except ParserError as e:
                raise ValueError(f"invalid query string: unknown date or datetime format '{v}'") from e
            if isinstance(field, tfields.DatetimeField):
                values[i] = dt if dt.tzinfo else dt.replace(tzinfo=datetime.UTC)
            else:
                values[i] = dt.date()
        if isinstance(field, tfields.BooleanField):
            try:
                values[i] = v.lower()[0] in ["t", "y"] or v == "1"
            except IndexError as e:
                raise ValueError("invalid query string") from e
    return values if isinstance(component.value, list) else values[0]


def _like_lookup(path: str, pattern: str) -> Q:
    """Maps a LIKE pattern onto Tortoise's case-insensitive lookups.

    Only patterns of the form x, %x, x% and %x% are supported; Tortoise has no general LIKE.
    """
    inner = pattern.strip("%")
    if "%" in inner or "_" in inner:
        raise ValueError(f"invalid query string: unsupported LIKE pattern '{pattern}'")
    starts, ends = pattern.startswith("%"), pattern.endswith("%")
    if starts and ends:
        return Q(**{f"{path}__icontains": inner})
    if ends:
        return Q(**{f"{path}__istartswith": inner})
    if starts:
        return Q(**{f"{path}__iendswith": inner})
    return Q(**{f"{path}__iexact": inner})


def _equals(attr: ResolvedAttribute, value: Any) -> Q:
    if value is None:
        return Q(**{f"{attr.path}__isnull": True})
    if attr.is_string:
        return Q(**{f"{attr.path}__iexact": value})
    return Q(**{attr.path: value})


def _any_of(attr: ResolvedAttribute, values: list[Any]) -> Q:
    if attr.is_string:
        return Q(*[_equals(attr, v) for v in values], join_type=Q.OR) if values else Q(id__in=[])
    return Q(**{f"{attr.path}__in": values})


class TortoiseQueryFilter:
    def __init__(self, filter_string: str) -> None:
        self.builder = QueryFilterBuilder(filter_string)

    @staticmethod
    def _exists(model: type[Model], condition: Q) -> Q:
        """Rows of ``model`` for which some related row satisfies ``condition``."""
        return Q(id__in=Subquery(model.filter(condition).values("id")))

    def _element(self, component: QueryFilterBuilderComponent, model: type[Model]) -> Q:
        attr = resolve_attribute(model, component.attribute_name)
        value = _validate(component, attr)
        rel = component.relationship
        path = attr.path

        if rel is RelationalKeyword.IS:
            condition = Q(**{f"{path}__isnull": True})
        elif rel is RelationalKeyword.IS_NOT:
            condition = Q(**{f"{path}__isnull": False})
        elif rel is RelationalKeyword.IN:
            condition = _any_of(attr, value)
        elif rel is RelationalKeyword.NOT_IN:
            if attr.through_relation:
                # no related row matches, rather than some related row does not match
                return ~self._exists(model, _any_of(attr, value))
            return ~_any_of(attr, value)
        elif rel is RelationalKeyword.CONTAINS_ALL:
            if len(value) == 1:
                condition = _any_of(attr, value)
            else:
                # each value must be matched by its own related row
                return Q(*[self._exists(model, _equals(attr, v)) for v in value], join_type=Q.AND)
        elif rel is RelationalKeyword.LIKE:
            condition = _like_lookup(path, value)
        elif rel is RelationalKeyword.NOT_LIKE:
            condition = ~_like_lookup(path, value)
        elif rel is RelationalOperator.EQ:
            condition = _equals(attr, value)
        elif rel is RelationalOperator.NOTEQ:
            condition = ~_equals(attr, value) & Q(**{f"{path}__isnull": False})
        elif rel is RelationalOperator.GT:
            condition = Q(**{f"{path}__gt": value})
        elif rel is RelationalOperator.LT:
            condition = Q(**{f"{path}__lt": value})
        elif rel is RelationalOperator.GTE:
            condition = Q(**{f"{path}__gte": value})
        elif rel is RelationalOperator.LTE:
            condition = Q(**{f"{path}__lte": value})
        else:
            raise ValueError(f"invalid relationship {rel}")

        return self._exists(model, condition) if attr.through_relation else condition

    @staticmethod
    def _consolidate(group: list[Q], operators: deque[LogicalOperator]) -> Q:
        result: Q | None = None
        for i, element in enumerate(reversed(group)):
            if not i:
                result = element
                continue
            operator = operators.pop()
            if operator is LogicalOperator.AND:
                result = Q(result, element, join_type=Q.AND)
            elif operator is LogicalOperator.OR:
                result = Q(result, element, join_type=Q.OR)
            else:
                raise ValueError(f"invalid logical operator {operator}")
        assert result is not None
        return result

    def condition(self, model: type[Model]) -> Q:
        b = self.builder
        partial: list[Q] = []
        stack: deque[list[Q]] = deque()
        operators: deque[LogicalOperator] = deque()
        for component in b.filter_components:
            if component == b.l_group_sep:
                stack.append(partial)
                partial = []
            elif component == b.r_group_sep:
                if partial:
                    complete = self._consolidate(partial, operators)
                    partial = stack.pop()
                    partial.append(complete)
                else:
                    partial = stack.pop()
            elif isinstance(component, LogicalOperator):
                operators.append(component)
            else:
                partial.append(self._element(component, model))  # type: ignore[arg-type]

        while True:
            consolidated = self._consolidate(partial, operators)
            if not stack:
                return consolidated
            partial = stack.pop()
            partial.append(consolidated)

    def apply[M: Model](self, query: QuerySet[M], model: type[M]) -> QuerySet[M]:
        return query.filter(self.condition(model))


def order_term[M: Model](
    query: QuerySet[M], model: type[M], attr_string: str, descending: bool
) -> tuple[QuerySet[M], str]:
    """Orders by an attribute string. A related attribute is reduced to one value per row (the
    lowest ascending, the highest descending), as the SQLAlchemy version does, so rows are
    never repeated.
    """
    attr = resolve_attribute(model, attr_string)
    if not attr.through_relation:
        name = "update_at" if attr.path == "updated_at" else attr.path
        return query, f"-{name}" if descending else name
    alias = f"_order_{attr.path}"
    aggregate = Max(attr.path) if descending else Min(attr.path)
    query = query.annotate(**{alias: aggregate})
    return query, f"-{alias}" if descending else alias
