"""Native async query helpers, rating recalculation and user ownership cleanup."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from tortoise import connections

from mealie.db.models.users import LongLiveToken, User, UserToRecipe
from mealie.db.models.users.password_reset import PasswordResetModel
from mealie.schema.response.pagination import PaginationQuery

from ._recipe_query import query_identifiers


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
    return await query_identifiers(model, pagination, group_id=group_id, household_id=household_id, randomize=False)


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
