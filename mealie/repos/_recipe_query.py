"""Compile the legacy public query language on the active async connection.

Only query metadata remains here until C7 removes the legacy SQL compiler.
Persistence and response hydration use native Tortoise models.
"""

import random
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, nulls_first, nulls_last, select
from sqlalchemy.dialects import postgresql, sqlite
from tortoise import connections

from mealie.schema._mealie import MealieModel
from mealie.schema.response.pagination import OrderByNullPosition, OrderDirection, PaginationQuery
from mealie.schema.response.query_search import SearchFilter
from mealie.services.query_filter.builder import NonFilterableValueError, QueryFilterBuilder


async def execute_select(query: Any) -> list[dict[str, Any]]:
    connection = connections.get("default")
    dialect = (
        postgresql.dialect(paramstyle="numeric_dollar")
        if connection.capabilities.dialect == "postgres"
        else sqlite.dialect()
    )
    compiled = query.compile(dialect=dialect)
    expanded = compiled.construct_expanded_state()
    processors = compiled._bind_processors | expanded.processors
    parameters = [
        processors[key](expanded.parameters[key]) if key in processors else expanded.parameters[key]
        for key in expanded.positiontup or []
    ]
    return await connection.execute_query_dict(expanded.statement, parameters)


class SearchSession:
    """Capture schema search settings without synchronous database access."""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    def get_bind(self) -> Any:
        return (
            postgresql.dialect() if connections.get("default").capabilities.dialect == "postgres" else sqlite.dialect()
        )

    def execute(self, statement: Any) -> None:
        self.statements.append(statement)

    async def apply(self) -> None:
        for statement in self.statements:
            await execute_select(statement)


async def query_identifiers(
    model: Any,
    pagination: PaginationQuery,
    *,
    group_id: UUID | None = None,
    household_id: UUID | None = None,
    search: str | None = None,
    schema: type[MealieModel] | None = None,
    column_aliases: dict[str, Any] | None = None,
    query: Any = None,
) -> list[Any]:
    if query is None:
        query = select(model.id)
        if group_id:
            query = query.filter_by(group_id=group_id)
        if household_id:
            query = query.filter_by(household_id=household_id)
    if search and schema:
        session = SearchSession()
        query = SearchFilter(session, search, schema._normalize_search).filter_query_by_search(query, schema, model)  # type: ignore[arg-type]
        await session.apply()
    if pagination.query_filter:
        query = QueryFilterBuilder(pagination.query_filter).filter_query(
            query, model=model, column_aliases=column_aliases
        )
    ordering = pagination.order_by or (None if search else "created_at")
    if ordering == "random":
        identifiers = list(dict.fromkeys(row["id"] for row in await execute_select(query)))
        if not identifiers:
            return []
        ranks = list(range(len(identifiers)))
        random.Random(pagination.pagination_seed).shuffle(ranks)
        # Append a seeded tie breaker after search/suggestion priorities, just
        # as the legacy repository did; shuffling the result would discard them.
        query = query.order_by(case(dict(zip(identifiers, ranks, strict=True)), value=model.id))
    elif ordering:
        for order in ordering.split(","):
            order = order.strip()
            try:
                if ":" in order:
                    attribute, direction_value = order.split(":")
                    direction = OrderDirection(direction_value)
                else:
                    attribute, direction = order, pagination.order_direction
                attr = QueryFilterBuilder.get_order_attr(
                    attribute, model, descending=direction is OrderDirection.desc, column_aliases=column_aliases
                )
                attr = attr.desc() if direction is OrderDirection.desc else attr.asc()
                if pagination.order_by_null_position is OrderByNullPosition.first:
                    attr = nulls_first(attr)
                elif pagination.order_by_null_position is OrderByNullPosition.last:
                    attr = nulls_last(attr)
                query = query.order_by(attr)
            except NonFilterableValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": {exc.message}'
                ) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": "{order}" is invalid'
                ) from exc
    return list(dict.fromkeys(row["id"] for row in await execute_select(query)))
