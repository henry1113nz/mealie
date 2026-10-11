"""Async public query execution using the native Tortoise model registry."""

import random
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from tortoise import Model, connections
from tortoise.transactions import in_transaction

from mealie.schema._mealie import MealieModel, SearchType
from mealie.schema.response.pagination import OrderByNullPosition, OrderDirection, PaginationQuery
from mealie.schema.response.query_search import SearchFilter
from mealie.services.query_filter.builder import NonFilterableValueError, QueryFilterBuilder
from mealie.services.query_filter.sql import Expression, NativeQuery, column, combine, compare


async def execute_select(query: NativeQuery) -> list[dict[str, Any]]:
    return await query.execute()


def apply_search(
    query: NativeQuery, model: type[Model], schema: type[MealieModel], parser: SearchFilter
) -> NativeQuery:
    if not schema._searchable_properties:
        raise AttributeError("Not Implemented")
    properties = [column(model, name) for name in schema._searchable_properties]
    if model.__name__ == "RecipeModel":
        properties = [column(model, "name_normalized"), column(model, "description_normalized")]
    if parser.search_type is SearchType.fuzzy:
        expressions = [Expression(f"{prop} %> ?", [parser.search]) for prop in properties]
        order = Expression(f"{properties[0]} <->> ?", [parser.search])
    else:
        expressions = [
            Expression(f"{prop} LIKE ?", [f"%{part}%"]) for prop in properties for part in parser.search_list
        ]
        order = Expression(f"{properties[0]} LIKE ? DESC", [f"%{parser.search}%"])
    if model.__name__ == "RecipeModel":
        for name in ("note_normalized", "original_text_normalized"):
            if parser.search_type is SearchType.fuzzy:
                expressions.append(compare(model, f"recipe_ingredient.{name}", "%>", parser.search))
            else:
                expressions.extend(
                    compare(model, f"recipe_ingredient.{name}", "LIKE", f"%{part}%") for part in parser.search_list
                )
    return query.filter(combine(expressions, "OR")).order_by(order)


async def _query_identifiers(
    model: type[Model],
    pagination: PaginationQuery,
    *,
    group_id: UUID | None = None,
    household_id: UUID | None = None,
    search: str | None = None,
    schema: type[MealieModel] | None = None,
    column_aliases: dict[str, Expression] | None = None,
    query: NativeQuery | None = None,
    randomize: bool = True,
) -> list[Any]:
    if query is None:
        query = NativeQuery(model)
        if group_id:
            path = (
                "report.group_id"
                if model.__name__ == "ReportEntryModel"
                else "user.group_id"
                if model.__name__ == "PasswordResetModel"
                else "group_id"
            )
            query.filter(compare(model, path, "=", group_id))
        if household_id:
            query.filter(compare(model, "household_id", "=", household_id))
    if search and schema:
        connection = connections.get("default")
        parser = SearchFilter(connection, search, schema._normalize_search)
        query = apply_search(query, model, schema, parser)
    if pagination.query_filter:
        query = QueryFilterBuilder(pagination.query_filter).filter_query(
            query, model=model, column_aliases=column_aliases
        )
    ordering = pagination.order_by or (None if search else "created_at")
    if ordering == "random" and randomize:
        identifiers = list(dict.fromkeys(row["id"] for row in await query.execute()))
        if not identifiers:
            return []
        ranks = list(range(len(identifiers)))
        random.Random(pagination.pagination_seed).shuffle(ranks)
        clauses = []
        values = []
        for identifier, rank in zip(identifiers, ranks, strict=True):
            clauses.append("WHEN ? THEN ?")
            values.extend([identifier, rank])
        query.order_by(Expression(f"CASE {column(model, 'id')} {' '.join(clauses)} END", values))
    elif ordering and ordering != "random":
        for order in ordering.split(","):
            order = order.strip()
            try:
                if ":" in order:
                    attribute, direction_value = order.split(":")
                    direction = OrderDirection(direction_value)
                else:
                    attribute, direction = order, pagination.order_direction
                expression = QueryFilterBuilder.get_order_attr(
                    attribute, model, descending=direction is OrderDirection.desc, column_aliases=column_aliases
                )
                expression = expression.desc() if direction is OrderDirection.desc else expression.asc()
                if pagination.order_by_null_position is OrderByNullPosition.first:
                    expression.sql += " NULLS FIRST"
                elif pagination.order_by_null_position is OrderByNullPosition.last:
                    expression.sql += " NULLS LAST"
                query.order_by(expression)
            except NonFilterableValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": {exc.message}'
                ) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": "{order}" is invalid'
                ) from exc
    return list(dict.fromkeys(row["id"] for row in await query.execute()))


async def query_identifiers(
    model: type[Model],
    pagination: PaginationQuery,
    *,
    group_id: UUID | None = None,
    household_id: UUID | None = None,
    search: str | None = None,
    schema: type[MealieModel] | None = None,
    column_aliases: dict[str, Expression] | None = None,
    query: NativeQuery | None = None,
    randomize: bool = True,
) -> list[Any]:
    """Pin PostgreSQL fuzzy-search settings and both random-order passes to one transaction."""
    kwargs: dict[str, Any] = {
        "group_id": group_id,
        "household_id": household_id,
        "search": search,
        "schema": schema,
        "column_aliases": column_aliases,
        "query": query,
        "randomize": randomize,
    }
    if search and schema:
        parser = SearchFilter(connections.get("default"), search, schema._normalize_search)
        if parser.search_type is SearchType.fuzzy:
            async with in_transaction("default") as connection:
                await connection.execute_query(
                    f"SET LOCAL pg_trgm.word_similarity_threshold = {float(schema._fuzzy_similarity_threshold)}"
                )
                return await _query_identifiers(model, pagination, **kwargs)
    return await _query_identifiers(model, pagination, **kwargs)
