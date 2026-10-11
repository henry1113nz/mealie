"""Temporary SQL bridges to domains that have not migrated to Tortoise yet.

All execution uses the current Tortoise connection/transaction. SQLAlchemy is
only used to compile the existing public query language against the remaining
relationship metadata; no synchronous session performs converted database access.
Group repositories reuse this compiler until the public relationship/filter
metadata moves in the remaining household and recipe conversions.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, nulls_first, nulls_last, select
from sqlalchemy.dialects import postgresql, sqlite
from tortoise import connections

from mealie.db.models._legacy_users import LongLiveToken, PasswordResetModel, User, UserToRecipe
from mealie.schema.response.pagination import OrderByNullPosition, OrderDirection, PaginationQuery
from mealie.services.query_filter.builder import NonFilterableValueError, QueryFilterBuilder


async def execute(sql: str, values: list[Any] | None = None) -> list[dict[str, Any]]:
    connection = connections.get("default")
    values = values or []
    postgres = connection.capabilities.dialect == "postgres"
    if postgres:
        parts = sql.split("?")
        sql = "".join(part + (f"${i + 1}" if i < len(parts) - 1 else "") for i, part in enumerate(parts))
    values = [
        (str(value) if postgres else value.hex)
        if isinstance(value, UUID)
        else value.astimezone(UTC).replace(tzinfo=None)
        if isinstance(value, datetime)
        else value
        for value in values
    ]
    return await connection.execute_query_dict(sql, values)


async def related_record(table: str, key: str, value: Any, **filters: Any) -> dict[str, Any] | None:
    # All identifiers are internal constants, never request input.
    filters = {key: value, **filters}
    conditions = " AND ".join(f'"{name}" = ?' for name in filters)
    results = await execute(f'SELECT * FROM "{table}" WHERE {conditions}', list(filters.values()))
    return results[0] if results else None


async def query_ids(model_name: str, group_id: UUID | None, pagination: PaginationQuery) -> list[Any]:
    model = {
        "User": User,
        "LongLiveToken": LongLiveToken,
        "PasswordResetModel": PasswordResetModel,
        "UserToRecipe": UserToRecipe,
    }[model_name]
    return await query_model_ids(model, group_id, pagination)


async def query_model_ids(
    model: Any, group_id: UUID | None, pagination: PaginationQuery, *, household_id: UUID | None = None
) -> list[Any]:
    query: Select = select(model.id)
    if group_id:
        # Password reset ownership is derived through its user as well.
        if model.__name__ == "ReportEntryModel":
            query = query.where(model.report.has(group_id=group_id))
        elif model is PasswordResetModel:
            query = query.where(model.user.has(User.group_id == group_id))
        else:
            query = query.filter_by(group_id=group_id)
    if household_id:
        query = query.filter_by(household_id=household_id)
    if pagination.query_filter:
        query = QueryFilterBuilder(pagination.query_filter).filter_query(query, model=model)
    ordering = pagination.order_by or "created_at"
    if ordering != "random":
        for order in ordering.split(","):
            order = order.strip()
            try:
                if ":" in order:
                    attribute, direction_value = order.split(":")
                    direction = OrderDirection(direction_value)
                else:
                    attribute, direction = order, pagination.order_direction
                attr = QueryFilterBuilder.get_order_attr(attribute, model, descending=direction is OrderDirection.desc)
                attr = attr.desc() if direction is OrderDirection.desc else attr.asc()
                if pagination.order_by_null_position is OrderByNullPosition.first:
                    attr = nulls_first(attr)
                elif pagination.order_by_null_position is OrderByNullPosition.last:
                    attr = nulls_last(attr)
                query = query.order_by(attr)
            except NonFilterableValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f'Invalid order_by statement "{pagination.order_by}": {exc.message}',
                ) from exc
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f'Invalid order_by statement "{pagination.order_by}": "{order}" is invalid',
                ) from exc

    connection = connections.get("default")
    dialect = (
        postgresql.dialect(paramstyle="numeric_dollar")
        if connection.capabilities.dialect == "postgres"
        else sqlite.dialect()
    )
    compiled = query.compile(dialect=dialect)
    expanded = compiled.construct_expanded_state()
    # Expanding IN parameters have individual names after compilation. Apply
    # their processors too, particularly UUIDs stored as SQLite hex strings.
    processors = compiled._bind_processors | expanded.processors
    parameters = [
        processors[key](expanded.parameters[key]) if key in processors else expanded.parameters[key]
        for key in expanded.positiontup or []
    ]
    rows = await connection.execute_query_dict(expanded.statement, parameters)
    return [row["id"] for row in rows]


async def refresh_recipe_rating(recipe_id: UUID) -> None:
    await execute(
        "UPDATE recipes SET rating = (SELECT AVG(rating) FROM users_to_recipes "
        "WHERE recipe_id = ? AND rating > 0), update_at = ? WHERE id = ?",
        [recipe_id, datetime.now(UTC), recipe_id],
    )


async def delete_user_dependents(user_id: UUID) -> None:
    """Retain legacy cascades on the same transaction as the user deletion."""
    # Recipes survive user deletion. Legacy SQLite could retain a dangling
    # owner ID; use the nullable owner column so the same operation also works
    # with enforced foreign keys on both databases. The group still owns the
    # recipe and will remove it if the group is subsequently deleted.
    await execute(
        "UPDATE recipes SET user_id = NULL, update_at = ? WHERE user_id = ?",
        [datetime.now(UTC), user_id],
    )
    from mealie.db.models.household import GroupMealPlan, ShoppingList

    connection = connections.get("default")
    for shopping_list in await ShoppingList.filter(user_id=user_id).using_db(connection):
        await shopping_list.delete(using_db=connection)
    await GroupMealPlan.filter(user_id=user_id).using_db(connection).delete()
    for table in ("recipe_comments", "recipe_timeline_events"):
        await execute(f'DELETE FROM "{table}" WHERE user_id = ?', [user_id])
