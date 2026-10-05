from __future__ import annotations

import re
from collections import deque
from typing import Any
from uuid import UUID

from dateutil import parser as date_parser
from dateutil.parser import ParserError
from fastapi import HTTPException
from humps import decamelize
from tortoise import fields
from tortoise.expressions import Q
from tortoise.models import Model
from tortoise.queryset import QuerySet

from mealie.schema._mealie.mealie_model import MealieModel

from .expressions import AttributeFilter
from .keywords import PlaceholderKeyword, RelationalKeyword
from .operators import LogicalOperator, RelationalOperator


class NonFilterableValueError(ValueError):
    """Raised when trying to filter by an unfilterable field"""

    def __init__(self, field: str):
        self.message = f"Cannot filter on {field}"
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}"


class QueryFilterJSONPart(MealieModel):
    left_parenthesis: str | None = None
    right_parenthesis: str | None = None
    logical_operator: LogicalOperator | None = None

    attribute_name: str | None = None
    relational_operator: RelationalKeyword | RelationalOperator | None = None
    value: str | list[str] | None = None


class QueryFilterJSON(MealieModel):
    parts: list[QueryFilterJSONPart] = []


class QueryFilterBuilderComponent:
    """A single relational statement"""

    raw_value: str | list[str] | None
    """The raw value parsed from the query filter string, before processing placeholder keywords"""

    value: str | list[str] | None
    """The value parsed from the query filter string, after processing placeholder keywords"""

    @staticmethod
    def strip_quotes_from_string(val: str) -> str:
        if len(val) > 2 and val[0] == '"' and val[-1] == '"':
            return val[1:-1]
        else:
            return val

    def __init__(
        self, attribute_name: str, relationship: RelationalKeyword | RelationalOperator, value: str | list[str]
    ) -> None:
        self.attribute_name = decamelize(attribute_name)
        self.relationship = relationship

        # remove encasing quotes
        if isinstance(value, str):
            value = self.strip_quotes_from_string(value)

        elif isinstance(value, list):
            value = [self.strip_quotes_from_string(v) for v in value]

        # validate relationship/value pairs
        if relationship in [
            RelationalKeyword.IN,
            RelationalKeyword.NOT_IN,
            RelationalKeyword.CONTAINS_ALL,
        ] and not isinstance(value, list):
            raise ValueError(
                f"invalid query string: {relationship.value} must be given a list of values"
                f"enclosed by {QueryFilterBuilder.l_list_sep} and {QueryFilterBuilder.r_list_sep}"
            )

        if relationship is RelationalKeyword.IS or relationship is RelationalKeyword.IS_NOT:
            if not isinstance(value, str) or value.lower() not in ["null", "none"]:
                raise ValueError(
                    f'invalid query string: "{relationship.value}" can only be used with "NULL", not "{value}"'
                )

            self.raw_value = None
        else:
            self.raw_value = value

        # process placeholder keywords
        self.value = PlaceholderKeyword.parse_value(self.raw_value)

    def __repr__(self) -> str:
        return f"[{self.attribute_name} {self.relationship.value} {self.value}]"

    def validate(self, model_attr_type: Any) -> Any:
        """Validate value against an model attribute's type and return a validated value, or raise a ValueError"""

        sanitized_values: list[Any]
        if not isinstance(self.value, list):
            sanitized_values = [self.value]
        else:
            sanitized_values = list(self.value)

        for i, v in enumerate(sanitized_values):
            # always allow querying for null values
            if v is None:
                continue

            if model_attr_type.field_type is str:
                sanitized_values[i] = v.lower()

            if self.relationship is RelationalKeyword.LIKE or self.relationship is RelationalKeyword.NOT_LIKE:
                if model_attr_type.field_type is not str:
                    raise ValueError(
                        f'invalid query string: "{self.relationship.value}" can only be used with string columns'
                    )

            if isinstance(model_attr_type, fields.UUIDField):
                try:
                    # we don't set value since a UUID is functionally identical to a string here
                    UUID(v)
                except ValueError as e:
                    raise ValueError(f"invalid query string: invalid UUID '{v}'") from e

            if isinstance(model_attr_type, fields.DateField | fields.DatetimeField):
                try:
                    dt = date_parser.parse(v)
                    sanitized_values[i] = dt.date() if isinstance(model_attr_type, fields.DateField) else dt
                except ParserError as e:
                    raise ValueError(f"invalid query string: unknown date or datetime format '{v}'") from e

            if isinstance(model_attr_type, fields.IntField | fields.SmallIntField | fields.BigIntField):
                sanitized_values[i] = int(v)
            elif isinstance(model_attr_type, fields.FloatField | fields.DecimalField):
                sanitized_values[i] = float(v)

            if isinstance(model_attr_type, fields.BooleanField):
                try:
                    sanitized_values[i] = v.lower()[0] in ["t", "y"] or v == "1"
                except IndexError as e:
                    raise ValueError("invalid query string") from e

        return sanitized_values if isinstance(self.value, list) else sanitized_values[0]

    def as_json_model(self) -> QueryFilterJSONPart:
        return QueryFilterJSONPart(
            left_parenthesis=None,
            right_parenthesis=None,
            logical_operator=None,
            attribute_name=self.attribute_name,
            relational_operator=self.relationship,
            value=self.raw_value,  # we use the raw value to preserve placeholder keywords
        )


RelationshipChain = list[str]


class QueryFilterBuilder:
    l_group_sep: str = "("
    r_group_sep: str = ")"
    group_seps: set[str] = {l_group_sep, r_group_sep}

    l_list_sep: str = "["
    r_list_sep: str = "]"
    list_item_sep: str = ","

    def __init__(self, filter_string: str) -> None:
        # parse filter string
        components = QueryFilterBuilder._break_filter_string_into_components(filter_string)
        base_components = QueryFilterBuilder._break_components_into_base_components(components)
        QueryFilterBuilder._validate_parenthesis(base_components)

        # parse base components into a filter group
        self.filter_components = QueryFilterBuilder._parse_base_components_into_filter_components(base_components)

    def __repr__(self) -> str:
        joined = " ".join(
            [
                str(component.value if isinstance(component, LogicalOperator) else component)
                for component in self.filter_components
            ],
        )

        return f"<<{joined}>>"

    @staticmethod
    def _validate_parenthesis(base_components: list[str | list[str]]) -> None:
        """Validate that every group is opened before it's closed, and that all groups are closed."""

        VALUE_ERROR = ValueError("invalid query string: parenthesis are unbalanced")

        depth = 0
        for base_component in base_components:
            if base_component == QueryFilterBuilder.l_group_sep:
                depth += 1
            elif base_component == QueryFilterBuilder.r_group_sep:
                depth -= 1
                if depth < 0:
                    raise VALUE_ERROR

        if depth:
            raise VALUE_ERROR

    @classmethod
    def combine_filters(cls, *filter_strings: str | None) -> str:
        """
        Combine filter strings into one filter string joined by `AND`, ignoring empty ones.

        Validates each sub-filter individually, throwing an HTTPException if any are invalid.
        """

        parts: list[str] = []
        for filter_string in filter_strings:
            if not filter_string:
                continue

            try:
                cls(filter_string)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

            parts.append(f"({filter_string})")

        return " AND ".join(parts)

    @classmethod
    def _consolidate_group(cls, group: list[Q], logical_operators: deque[LogicalOperator]) -> Q:
        if not group:
            raise ValueError("invalid query string")
        result = group[-1]
        for element in reversed(group[:-1]):
            if not logical_operators:
                raise ValueError("invalid query string")
            operator = logical_operators.pop()
            result = result & element if operator is LogicalOperator.AND else result | element
        return result

    @classmethod
    def resolve_attribute(cls, attr_string: str, model: type[Model]) -> tuple[str, Any, bool]:
        """Resolve public dotted paths, including tenant association properties."""
        links = deque(decamelize(attr_string).replace("__", ".").split("."))
        current = model
        path: list[str] = []
        related = False
        while links:
            link = links.popleft()
            if link == "updated_at":
                link = "update_at"
            proxy = getattr(current, "__association_proxies__", {}).get(link)
            if proxy:
                links.extendleft(reversed(proxy))
                continue
            field = current._meta.fields_map.get(link)
            if field is None:
                raise ValueError(f"invalid attribute string: '{attr_string}' does not exist on this schema")
            path.append(link)
            if links:
                target = getattr(field, "related_model", None)
                if target is None:
                    raise ValueError(f"invalid attribute string: '{attr_string}' does not exist on this schema")
                current = target
                related = True
            elif link not in getattr(current, "__filterable_fields__", set()) | {"created_at", "update_at"}:
                raise NonFilterableValueError(attr_string)
        return "__".join(path), field, related

    @classmethod
    def get_model_and_model_attr_from_attr_string(
        cls, attr_string: str, model: type[Model], *, collect_relationships: RelationshipChain | None = None
    ) -> tuple[type[Model], Any]:
        path, field, related = cls.resolve_attribute(attr_string, model)
        if collect_relationships is not None and related:
            collect_relationships.extend(path.split("__")[:-1])
        return field.model, field

    @classmethod
    def get_order_attr(
        cls,
        attr_string: str,
        model: type[Model],
        *,
        descending: bool,
        column_aliases: dict[str, Any] | None = None,
    ) -> str:
        path, _, _ = cls.resolve_attribute(attr_string, model)
        return (column_aliases or {}).get(path, path)

    @classmethod
    def _component_filter(
        cls, component: QueryFilterBuilderComponent, model: type[Model], aliases: dict[str, str]
    ) -> Q:
        path, field, related = cls.resolve_attribute(component.attribute_name, model)
        path = aliases.get(path, path)
        value = component.validate(field)
        relationship = component.relationship
        is_string = field.field_type is str

        def matching(lookup: str, val: Any) -> Q:
            return AttributeFilter(path, lookup, val, string=is_string)

        equal = ""
        if relationship is RelationalKeyword.IS:
            return matching("isnull", True)
        if relationship is RelationalKeyword.IS_NOT:
            return matching("isnull", False)
        if relationship in (RelationalKeyword.IN, RelationalKeyword.NOT_IN):
            condition = matching("in", value)
            return ~condition if relationship is RelationalKeyword.NOT_IN else condition
        if relationship is RelationalKeyword.CONTAINS_ALL:
            condition = Q()
            for item in value:
                condition &= matching(equal, item)
            return condition
        if relationship in (RelationalKeyword.LIKE, RelationalKeyword.NOT_LIKE):
            return matching("not_like" if relationship is RelationalKeyword.NOT_LIKE else "like", value)
        operators = {
            RelationalOperator.EQ: equal,
            RelationalOperator.NOTEQ: "not",
            RelationalOperator.GT: "gt",
            RelationalOperator.GTE: "gte",
            RelationalOperator.LT: "lt",
            RelationalOperator.LTE: "lte",
        }
        condition = matching(operators[relationship], value)
        return condition

    def filter_query(
        self, query: QuerySet, model: type[Model], column_aliases: dict[str, str] | None = None
    ) -> QuerySet:
        if not self.filter_components:
            return query
        partial_group: list[Q] = []
        partial_group_stack: deque[list[Q]] = deque()
        logical_operator_stack: deque[LogicalOperator] = deque()
        for component in self.filter_components:
            if component == self.l_group_sep:
                partial_group_stack.append(partial_group)
                partial_group = []
            elif component == self.r_group_sep:
                complete = self._consolidate_group(partial_group, logical_operator_stack)
                partial_group = partial_group_stack.pop()
                partial_group.append(complete)
            elif isinstance(component, LogicalOperator):
                logical_operator_stack.append(component)
            elif isinstance(component, QueryFilterBuilderComponent):
                partial_group.append(self._component_filter(component, model, column_aliases or {}))
            else:
                raise ValueError("invalid query string")
        return query.filter(self._consolidate_group(partial_group, logical_operator_stack))

    @staticmethod
    def _break_filter_string_into_components(filter_string: str) -> list[str]:
        """Recursively break filter string into components based on parenthesis groupings"""
        components = [filter_string]
        in_quotes = False
        while True:
            subcomponents = []
            for component in components:
                # don't parse components comprised of only a separator
                if component in QueryFilterBuilder.group_seps:
                    subcomponents.append(component)
                    continue

                # construct a component until it hits the right separator
                new_component = ""
                for c in component:
                    # ignore characters in-between quotes
                    if c == '"':
                        in_quotes = not in_quotes

                    if c in QueryFilterBuilder.group_seps and not in_quotes:
                        if new_component:
                            subcomponents.append(new_component)

                        subcomponents.append(c)
                        new_component = ""
                        continue

                    new_component += c

                if new_component:
                    subcomponents.append(new_component.strip())

            if components == subcomponents:
                break

            components = subcomponents

        return components

    @staticmethod
    def _break_components_into_base_components(components: list[str]) -> list[str | list[str]]:
        """Further break down components by splitting at relational and logical operators"""
        pattern = "|".join([f"\\b{operator.value}\\b" for operator in LogicalOperator])
        logical_operators = re.compile(f"({pattern})", flags=re.IGNORECASE)

        in_list = False
        base_components: list[str | list] = []
        list_value_components = []
        for component in components:
            # parse out lists as their own singular sub component
            subcomponents = component.split(QueryFilterBuilder.l_list_sep)
            for i, subcomponent in enumerate(subcomponents):
                if not i:
                    continue

                for j, list_value_string in enumerate(subcomponent.split(QueryFilterBuilder.r_list_sep)):
                    if j % 2:
                        continue

                    list_value_components.append(
                        [val.strip() for val in list_value_string.split(QueryFilterBuilder.list_item_sep)]
                    )

            quote_offset = 0
            subcomponents = component.split('"')
            for i, subcomponent in enumerate(subcomponents):
                # we are in a list subcomponent, which is already handled
                if in_list:
                    if QueryFilterBuilder.r_list_sep in subcomponent:
                        # filter out the remainder of the list subcomponent and continue parsing
                        base_components.append(list_value_components.pop(0))
                        subcomponent = subcomponent.split(QueryFilterBuilder.r_list_sep, maxsplit=1)[-1].strip()
                        in_list = False
                    else:
                        continue

                # don't parse components comprised of only a separator
                if subcomponent in QueryFilterBuilder.group_seps:
                    quote_offset += 1
                    base_components.append(subcomponent)
                    continue

                # this subcomponent was surrounded in quotes, so we keep it as-is
                if (i + quote_offset) % 2:
                    base_components.append(f'"{subcomponent.strip()}"')
                    continue

                # if the final subcomponent has quotes, it creates an extra empty subcomponent at the end
                if not subcomponent:
                    continue

                # continue parsing this subcomponent up to the list, then skip over subsequent subcomponents
                if not in_list and QueryFilterBuilder.l_list_sep in subcomponent:
                    subcomponent, _new_sub_component = subcomponent.split(QueryFilterBuilder.l_list_sep, maxsplit=1)
                    subcomponent = subcomponent.strip()
                    subcomponents.insert(i + 1, _new_sub_component)
                    quote_offset += 1
                    in_list = True

                # parse out logical operators
                new_components = [
                    base_component.strip() for base_component in logical_operators.split(subcomponent) if base_component
                ]

                # parse out relational keywords and operators
                # each base_subcomponent has exactly zero or one keyword or operator
                for component in new_components:
                    if not component:
                        continue

                    # we try relational operators first since they aren't required to be surrounded by spaces
                    parsed_component = RelationalOperator.parse_component(component)
                    if parsed_component is not None:
                        base_components.extend(parsed_component)
                        continue

                    parsed_component = RelationalKeyword.parse_component(component)
                    if parsed_component is not None:
                        base_components.extend(parsed_component)
                        continue

                    # this component does not have any keywords or operators, so we just add it as-is
                    base_components.append(component)

        return base_components

    @staticmethod
    def _parse_base_components_into_filter_components(
        base_components: list[str | list[str]],
    ) -> list[str | QueryFilterBuilderComponent | LogicalOperator]:
        """Walk through base components and construct filter collections"""
        relational_keywords = [kw.value for kw in RelationalKeyword]
        relational_operators = [op.value for op in RelationalOperator]
        logical_operators = [op.value for op in LogicalOperator]

        # parse QueryFilterComponents and logical operators
        components: list[str | QueryFilterBuilderComponent | LogicalOperator] = []
        for i, base_component in enumerate(base_components):
            if isinstance(base_component, list):
                continue

            if base_component in QueryFilterBuilder.group_seps:
                components.append(base_component)

            elif base_component in relational_keywords or base_component in relational_operators:
                relationship: RelationalKeyword | RelationalOperator
                if base_component in relational_keywords:
                    relationship = RelationalKeyword(base_components[i])
                else:
                    relationship = RelationalOperator(base_components[i])

                components.append(
                    QueryFilterBuilderComponent(
                        attribute_name=base_components[i - 1],  # type: ignore
                        relationship=relationship,
                        value=base_components[i + 1],
                    )
                )

            elif base_component.upper() in logical_operators:
                components.append(LogicalOperator(base_component.upper()))

        return components

    def as_json_model(self) -> QueryFilterJSON:
        parts: list[QueryFilterJSONPart] = []

        current_part: QueryFilterJSONPart | None = None
        left_parens: list[str] = []
        right_parens: list[str] = []
        last_logical_operator: LogicalOperator | None = None

        def add_part():
            nonlocal current_part, left_parens, right_parens, last_logical_operator
            if not current_part:
                return

            current_part.left_parenthesis = "".join(left_parens) or None
            current_part.right_parenthesis = "".join(right_parens) or None
            current_part.logical_operator = last_logical_operator

            parts.append(current_part)
            current_part = None
            left_parens.clear()
            right_parens.clear()
            last_logical_operator = None

        for component in self.filter_components:
            if isinstance(component, QueryFilterBuilderComponent):
                if current_part:
                    add_part()
                current_part = component.as_json_model()

            elif isinstance(component, LogicalOperator):
                if current_part:
                    add_part()
                last_logical_operator = component

            elif isinstance(component, str):
                if component == QueryFilterBuilder.l_group_sep:
                    left_parens.append(component)
                elif component == QueryFilterBuilder.r_group_sep:
                    right_parens.append(component)

        # add last part, if any
        add_part()
        return QueryFilterJSON(parts=parts)
