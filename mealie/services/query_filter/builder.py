from __future__ import annotations

import re
from collections import deque
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from dateutil import parser as date_parser
from dateutil.parser import ParserError
from fastapi import HTTPException
from humps import decamelize
from tortoise import Model, fields

from mealie.schema._mealie.mealie_model import MealieModel

from .keywords import PlaceholderKeyword, RelationalKeyword
from .metadata import FILTERABLE_FIELDS
from .operators import LogicalOperator, RelationalOperator
from .sql import Expression, NativeQuery, Relation, combine, field_expression, resolve, wrap


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

            if isinstance(model_attr_type, (fields.CharField, fields.TextField)):
                sanitized_values[i] = v.lower()

            if self.relationship is RelationalKeyword.LIKE or self.relationship is RelationalKeyword.NOT_LIKE:
                if not isinstance(model_attr_type, (fields.CharField, fields.TextField)):
                    raise ValueError(
                        f'invalid query string: "{self.relationship.value}" can only be used with string columns'
                    )

            if isinstance(model_attr_type, fields.UUIDField):
                try:
                    sanitized_values[i] = UUID(v)
                except ValueError as e:
                    raise ValueError(f"invalid query string: invalid UUID '{v}'") from e

            if isinstance(model_attr_type, (fields.IntField, fields.SmallIntField, fields.BigIntField)):
                sanitized_values[i] = int(v)
            elif isinstance(model_attr_type, fields.FloatField):
                sanitized_values[i] = float(v)
            elif isinstance(model_attr_type, fields.DecimalField):
                sanitized_values[i] = Decimal(v)

            if isinstance(model_attr_type, fields.DateField | fields.DatetimeField):
                try:
                    dt = date_parser.parse(v)
                    sanitized_values[i] = dt.date() if isinstance(model_attr_type, fields.DateField) else dt
                except ParserError as e:
                    raise ValueError(f"invalid query string: unknown date or datetime format '{v}'") from e

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


RelationshipChain = list[Relation]


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
    def _consolidate_group(cls, group: list[Expression], logical_operators: deque[LogicalOperator]) -> Expression:
        result = Expression("TRUE")
        for i, element in enumerate(reversed(group)):
            if not i:
                result = element
            else:
                operator = logical_operators.pop()
                result = result & element if operator is LogicalOperator.AND else result | element
        return result

    @classmethod
    def get_model_and_model_attr_from_attr_string(
        cls,
        attr_string: str,
        model: type[Model],
        *,
        collect_relationships: RelationshipChain | None = None,
    ) -> tuple[type[Model], fields.Field]:
        try:
            nested, item, relations = resolve(model, decamelize(attr_string))
        except (KeyError, AttributeError) as exc:
            raise ValueError(f"invalid attribute string: '{attr_string}' does not exist on this schema") from exc
        allowed = {*FILTERABLE_FIELDS.get(nested.__name__, []), "created_at", "update_at"}
        if nested.__name__ in ("ApiExtras", "IngredientFoodExtras", "ShoppingListExtras", "ShoppingListItemExtras"):
            allowed.update(FILTERABLE_FIELDS["ExtrasGeneric"])
        if item.model_field_name not in allowed:
            raise NonFilterableValueError(attr_string)
        if collect_relationships is not None:
            collect_relationships.extend(relations)
        return nested, item

    @classmethod
    def get_order_attr(
        cls,
        attr_string: str,
        model: type[Model],
        *,
        descending: bool,
        column_aliases: dict[str, Expression] | None = None,
    ) -> Expression:
        relations: RelationshipChain = []
        nested, item = cls.get_model_and_model_attr_from_attr_string(
            attr_string, model, collect_relationships=relations
        )
        if column_aliases and (alias := column_aliases.get(item.model_field_name)) is not None:
            return alias
        expression = field_expression(nested, item, alias=relations[-1].target_alias if relations else None)
        if not relations:
            return expression
        aggregate = "MAX" if descending else "MIN"
        tables = ", ".join(dict.fromkeys(edge.from_sql for edge in relations))
        joins = " AND ".join(edge.condition for edge in relations)
        return Expression(f"(SELECT {aggregate}({expression.sql}) FROM {tables} WHERE {joins})")

    @classmethod
    def _get_filter_element(
        cls,
        component: QueryFilterBuilderComponent,
        model: type[Model],
        model_attr: fields.Field,
        model_attr_type: Any,
        relationships: RelationshipChain,
        expression: Expression | None = None,
    ) -> Expression:
        expression = expression or field_expression(
            model, model_attr, alias=relationships[-1].target_alias if relationships else None
        )
        value = component.validate(model_attr_type)
        sql, parameters = expression.sql, expression.parameters
        relationship = component.relationship
        if relationship in (RelationalKeyword.IS, RelationalKeyword.IS_NOT):
            element = Expression(
                f"{sql} IS {'NOT ' if relationship is RelationalKeyword.IS_NOT else ''}NULL", parameters
            )
        elif relationship in (RelationalKeyword.IN, RelationalKeyword.NOT_IN, RelationalKeyword.CONTAINS_ALL):
            if relationship is RelationalKeyword.CONTAINS_ALL and len(value) != 1:
                return combine([wrap(Expression(f"{sql} = ?", parameters + [v]), relationships) for v in value])
            element = (
                Expression(f"{sql} IN ({', '.join('?' for _ in value)})", parameters + value)
                if value
                else Expression("FALSE")
            )
            if relationship is RelationalKeyword.NOT_IN:
                return ~wrap(element, relationships)
        elif relationship in (RelationalKeyword.LIKE, RelationalKeyword.NOT_LIKE):
            element = Expression(
                f"{sql} {'NOT ' if relationship is RelationalKeyword.NOT_LIKE else ''}LIKE ?", parameters + [value]
            )
        else:
            operators = {
                RelationalOperator.EQ: "=",
                RelationalOperator.NOTEQ: "!=",
                RelationalOperator.GT: ">",
                RelationalOperator.LT: "<",
                RelationalOperator.GTE: ">=",
                RelationalOperator.LTE: "<=",
            }
            if isinstance(value, bool):
                element = Expression(f"{sql} {operators[relationship]} {'TRUE' if value else 'FALSE'}", parameters)
            else:
                element = Expression(f"{sql} {operators[relationship]} ?", parameters + [value])
        return wrap(element, relationships)

    def filter_query(
        self, query: NativeQuery, model: type[Model], column_aliases: dict[str, Expression] | None = None
    ) -> NativeQuery:
        column_aliases = column_aliases or {}
        attr_map: dict[int, tuple[type[Model], fields.Field, RelationshipChain]] = {}
        for i, component in enumerate(self.filter_components):
            if not isinstance(component, QueryFilterBuilderComponent):
                continue
            relations: RelationshipChain = []
            nested, item = self.get_model_and_model_attr_from_attr_string(
                component.attribute_name, model, collect_relationships=relations
            )
            attr_map[i] = nested, item, relations
        partial_group: list[Expression] = []
        partial_group_stack: deque[list[Expression]] = deque()
        logical_operator_stack: deque[LogicalOperator] = deque()
        for i, component in enumerate(self.filter_components):
            if component == self.l_group_sep:
                partial_group_stack.append(partial_group)
                partial_group = []
            elif component == self.r_group_sep:
                if partial_group:
                    complete_group = self._consolidate_group(partial_group, logical_operator_stack)
                    partial_group = partial_group_stack.pop()
                    partial_group.append(complete_group)
                else:
                    partial_group = partial_group_stack.pop()
            elif isinstance(component, LogicalOperator):
                logical_operator_stack.append(component)
            else:
                component = cast(QueryFilterBuilderComponent, component)
                nested, item, relations = attr_map[i]
                alias = column_aliases.get(component.attribute_name.split(".")[-1])
                if alias is not None:
                    relations = []
                partial_group.append(self._get_filter_element(component, nested, item, item, relations, alias))
        while True:
            consolidated = self._consolidate_group(partial_group, logical_operator_stack)
            if not partial_group_stack:
                return query.filter(consolidated)
            partial_group = partial_group_stack.pop()
            partial_group.append(consolidated)

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
