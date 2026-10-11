"""Read C6 recipe data on the household repository's active async transaction.

These projections disappear when recipe persistence becomes native in C6. They
preserve the existing response shapes without opening a second database session.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mealie.db.models.users.users import User

from . import _users_coexistence as bridge


def _timestamps(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("created_at", "update_at", "date_updated", "last_made"):
        value = data.get(key)
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if isinstance(value, datetime):
            data[key] = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return data


async def recipe_summary(recipe_id: UUID | str | None) -> dict[str, Any] | None:
    if recipe_id is None:
        return None
    recipe = await bridge.related_record("recipes", "id", UUID(str(recipe_id)))
    if recipe is None:
        return None
    user = await User.get_or_none(id=recipe["user_id"]) if recipe["user_id"] else None
    recipe["household_id"] = user.household_id if user else None
    for field, table, association, column in (
        ("recipe_category", "categories", "recipes_to_categories", "category_id"),
        ("tags", "tags", "recipes_to_tags", "tag_id"),
        ("tools", "tools", "recipes_to_tools", "tool_id"),
    ):
        recipe[field] = await bridge.execute(
            f'SELECT item.* FROM "{table}" item JOIN "{association}" link '
            f'ON item.id = link."{column}" WHERE link.recipe_id = ?',
            [UUID(str(recipe_id))],
        )
    for tool in recipe["tools"]:
        tool["households_with_tool"] = [
            row["slug"]
            for row in await bridge.execute(
                "SELECT households.slug FROM households JOIN households_to_tools link "
                "ON households.id = link.household_id WHERE link.tool_id = ?",
                [UUID(str(tool["id"]))],
            )
        ]
    return _timestamps(recipe)


async def label(label_id: UUID | str | None) -> dict[str, Any] | None:
    if label_id is None:
        return None
    return await bridge.related_record("multi_purpose_labels", "id", UUID(str(label_id)))


async def ingredient_unit(unit_id: UUID | str | None) -> dict[str, Any] | None:
    if unit_id is None:
        return None
    unit = await bridge.related_record("ingredient_units", "id", UUID(str(unit_id)))
    if unit is None:
        return None
    unit["aliases"] = await bridge.execute(
        "SELECT name FROM ingredient_units_aliases WHERE unit_id = ?", [UUID(str(unit_id))]
    )
    return _timestamps(unit)


async def ingredient_food(food_id: UUID | str | None) -> dict[str, Any] | None:
    if food_id is None:
        return None
    food_id = UUID(str(food_id))
    food = await bridge.related_record("ingredient_foods", "id", food_id)
    if food is None:
        return None
    food["label"] = await label(food["label_id"])
    food["extras"] = {
        row["key_name"]: row["value"]
        for row in await bridge.execute("SELECT * FROM ingredient_food_extras WHERE ingredient_food_id = ?", [food_id])
    }
    food["aliases"] = await bridge.execute("SELECT name FROM ingredient_foods_aliases WHERE food_id = ?", [food_id])
    food["households_with_ingredient_food"] = [
        row["slug"]
        for row in await bridge.execute(
            "SELECT households.slug FROM households JOIN households_to_ingredient_foods link "
            "ON households.id = link.household_id WHERE link.food_id = ?",
            [food_id],
        )
    ]
    food["substitutions"] = await bridge.execute(
        "SELECT * FROM ingredient_foods_substitutions WHERE food_id = ? ORDER BY position", [food_id]
    )
    for substitution in food["substitutions"]:
        substitute_id = substitution["substitute_food_id"]
        substitution["substitute_food"] = (
            await bridge.related_record("ingredient_foods", "id", UUID(str(substitute_id))) if substitute_id else None
        )
    return _timestamps(food)
