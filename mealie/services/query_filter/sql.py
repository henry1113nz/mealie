"""Parameterized public queries built from native Tortoise model metadata.

Correlated EXISTS and aggregate subqueries preserve one result per root row,
including filters that independently match different members of a collection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from tortoise import Model, connections, fields
from tortoise.fields.relational import BackwardFKRelation, ForeignKeyFieldInstance, ManyToManyFieldInstance

from .metadata import FIELD_ALIASES


@dataclass
class Expression:
    sql: str
    parameters: list[Any] = field(default_factory=list)

    def __and__(self, other: Expression) -> Expression:
        return Expression(f"({self.sql} AND {other.sql})", self.parameters + other.parameters)

    def __or__(self, other: Expression) -> Expression:
        return Expression(f"({self.sql} OR {other.sql})", self.parameters + other.parameters)

    def __invert__(self) -> Expression:
        return Expression(f"NOT ({self.sql})", self.parameters)

    def asc(self) -> Expression:
        return Expression(self.sql + " ASC", self.parameters)

    def desc(self) -> Expression:
        return Expression(self.sql + " DESC", self.parameters)


def combine(expressions: list[Expression], operator: str = "AND") -> Expression:
    if not expressions:
        return Expression("TRUE" if operator == "AND" else "FALSE")
    return Expression(
        "(" + f" {operator} ".join(item.sql for item in expressions) + ")",
        [value for item in expressions for value in item.parameters],
    )


def column(model: type[Model], name: str, alias: str | None = None) -> str:
    return f'"{alias or model._meta.db_table}"."{model._meta.fields_db_projection.get(name, name)}"'


@dataclass
class Relation:
    source: type[Model]
    target: type[Model]
    from_sql: str
    condition: str
    target_alias: str


def relation(model: type[Model], name: str, source_alias: str, used: dict[str, int]) -> Relation:
    # These public read-only associations carry predicates that a native M2M
    # descriptor cannot express. All foreign keys still belong to native models.
    virtual = {
        ("RecipeModel", "rated_by"): ("User", "users_to_recipes", "recipe_id", "user_id", ""),
        ("RecipeModel", "favorited_by"): (
            "User",
            "users_to_recipes",
            "recipe_id",
            "user_id",
            " AND users_to_recipes.is_favorite = TRUE",
        ),
        ("RecipeModel", "made_by"): ("Household", "households_to_recipes", "recipe_id", "household_id", ""),
        ("User", "rated_recipes"): ("RecipeModel", "users_to_recipes", "user_id", "recipe_id", ""),
        ("User", "favorite_recipes"): (
            "RecipeModel",
            "users_to_recipes",
            "user_id",
            "recipe_id",
            " AND users_to_recipes.is_favorite = TRUE",
        ),
        ("Household", "made_recipes"): ("RecipeModel", "households_to_recipes", "household_id", "recipe_id", ""),
    }
    spec = virtual.get((model.__name__, name))
    if spec:
        from tortoise import Tortoise

        target = Tortoise.apps["models"][spec[0]]
        item = None
    else:
        item = model._meta.fields_map[name]
        target = item.related_model
    table_name = target._meta.db_table
    count = used.get(table_name, 0)
    used[table_name] = count + 1
    target_alias = f"{table_name}_q{count}" if count else table_name
    target_from = f'"{table_name}"' + (f' AS "{target_alias}"' if count else "")
    source_id = column(model, "id", source_alias)
    target_id = column(target, "id", target_alias)
    if spec or isinstance(item, ManyToManyFieldInstance):
        if spec:
            table, back, forward, extra = spec[1:]
        else:
            assert isinstance(item, ManyToManyFieldInstance)
            table, back, forward, extra = item.through, item.backward_key, item.forward_key, ""
        through_count = used.get(table, 0)
        used[table] = through_count + 1
        through_alias = f"{table}_q{through_count}" if through_count else table
        through_from = f'"{table}"' + (f' AS "{through_alias}"' if through_count else "")
        extra = extra.replace(table + ".", f'"{through_alias}".')
        condition = f'{source_id} = "{through_alias}"."{back}" AND {target_id} = "{through_alias}"."{forward}"{extra}'
        return Relation(model, target, target_from + ", " + through_from, condition, target_alias)
    if isinstance(item, BackwardFKRelation):
        condition = (
            f"{column(model, item.to_field_instance.model_field_name, source_alias)} = "
            f"{column(target, item.relation_field, target_alias)}"
        )
    elif isinstance(item, ForeignKeyFieldInstance):
        condition = (
            f"{column(target, item.to_field_instance.model_field_name, target_alias)} = "
            f"{column(model, item.source_field, source_alias)}"
        )
    else:
        raise KeyError(name)
    return Relation(model, target, target_from, condition, target_alias)


def resolve(model: type[Model], path: str) -> tuple[type[Model], fields.Field, list[Relation]]:
    parts = path.split(".")
    relations: list[Relation] = []
    current = model
    source_alias = model._meta.db_table
    used = {source_alias: 1}
    while parts:
        name = parts.pop(0)
        if name == "updated_at":
            name = "update_at"
        if alias := FIELD_ALIASES.get(current.__name__, {}).get(name):
            parts = alias.split(".") + parts
            continue
        if not parts:
            item = current._meta.fields_map.get(name)
            if item is not None and item.has_db_field:
                return current, item, relations
        edge = relation(current, name, source_alias, used)
        relations.append(edge)
        current = edge.target
        source_alias = edge.target_alias
    raise KeyError(path)


def wrap(expression: Expression, relations: list[Relation]) -> Expression:
    for item in reversed(relations):
        expression = Expression(
            f"EXISTS (SELECT 1 FROM {item.from_sql} WHERE {item.condition} AND {expression.sql})", expression.parameters
        )
    return expression


def field_expression(
    model: type[Model], item: fields.Field, *, normalize: bool = True, alias: str | None = None
) -> Expression:
    sql = column(model, item.model_field_name, alias)
    if normalize and isinstance(item, (fields.CharField, fields.TextField)):
        sql = f"LOWER({sql})"
    return Expression(sql)


def prepare_value(value: Any, dialect: str) -> Any:
    if isinstance(value, UUID):
        return str(value) if dialect == "postgres" else value.hex
    if isinstance(value, datetime):
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        value = value.replace(tzinfo=None)
        return value if dialect == "postgres" else value.isoformat(" ")
    if isinstance(value, date):
        return value if dialect == "postgres" else value.isoformat()
    return value


class NativeQuery:
    def __init__(self, model: type[Model]) -> None:
        self.model = model
        self.conditions: list[Expression] = []
        self.ordering: list[Expression] = []

    def filter(self, *expressions: Expression) -> NativeQuery:
        self.conditions.extend(expressions)
        return self

    where = filter

    def order_by(self, *expressions: Expression) -> NativeQuery:
        self.ordering.extend(expressions)
        return self

    def compile(self, compile_kwargs: dict[str, Any] | None = None) -> str:
        # A readable rendering for diagnostics; execution always binds parameters.
        sql, values = self.statement()
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            for value in values:
                sql = sql.replace("?", repr(value), 1)
        return sql.replace('"', "")

    def statement(self) -> tuple[str, list[Any]]:
        sql = f'SELECT {column(self.model, "id")} AS id FROM "{self.model._meta.db_table}"'
        values = []
        if self.conditions:
            expression = combine(self.conditions)
            sql += " WHERE " + expression.sql
            values.extend(expression.parameters)
        if self.ordering:
            sql += " ORDER BY " + ", ".join(expression.sql for expression in self.ordering)
            values.extend(value for expression in self.ordering for value in expression.parameters)
        return sql, values

    async def execute(self) -> list[dict[str, Any]]:
        connection = connections.get("default")
        sql, values = self.statement()
        dialect = connection.capabilities.dialect
        if dialect == "postgres":
            parts = sql.split("?")
            sql = "".join(
                part
                + ((f"${i + 1}::UUID" if isinstance(values[i], UUID) else f"${i + 1}") if i < len(parts) - 1 else "")
                for i, part in enumerate(parts)
            )
        return await connection.execute_query_dict(sql, [prepare_value(value, dialect) for value in values])


def select(model: type[Model]) -> NativeQuery:
    return NativeQuery(model)


def compare(model: type[Model], path: str, operator: str, value: Any = None) -> Expression:
    nested, item, relations = resolve(model, path)
    left = field_expression(nested, item, normalize=False, alias=relations[-1].target_alias if relations else None).sql
    if operator in ("IS NULL", "IS NOT NULL"):
        expression = Expression(f"{left} {operator}")
    elif operator in ("IN", "NOT IN"):
        values = list(value)
        expression = (
            Expression(f"{left} {operator} ({', '.join('?' for _ in values)})", values)
            if values
            else Expression("FALSE" if operator == "IN" else "TRUE")
        )
    else:
        expression = Expression(f"{left} {operator} ?", [value])
    return wrap(expression, relations)
