"""Transactional group deletion while recipe models remain legacy.

Only model metadata comes from SQLAlchemy; every statement executes through the
active Tortoise transaction. C6 replaces the explicit recipe ownership map as those
models gain native relations and deletion behavior.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.sql.ddl import sort_tables
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError

from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models.group.ai_providers import AIProvider, AIProviderHeaders, AIProviderParams, AIProviderSettings
from mealie.db.models.group.exports import GroupDataExportsModel
from mealie.db.models.group.preferences import GroupPreferencesModel
from mealie.db.models.group.report import ReportEntryModel, ReportModel
from mealie.db.models.server.task import ServerTaskModel
from mealie.db.models.users.users import User

# Tables without their own group_id use these ownership edges. Foreign keys
# such as ingredient.food_id and ingredient.referenced_recipe_id are references,
# not ownership, and must never make another group's recipe a deletion target.
_OWNERS: dict[str, tuple[str, str]] = {
    "households_to_ingredient_foods": ("food_id", "ingredient_foods"),
    "households_to_tools": ("tool_id", "tools"),
    "plan_rules_to_categories": ("category_id", "categories"),
    "plan_rules_to_tags": ("tag_id", "tags"),
    "cookbooks_to_categories": ("category_id", "categories"),
    "cookbooks_to_tags": ("tag_id", "tags"),
    "cookbooks_to_tools": ("tool_id", "tools"),
    "recipes_to_categories": ("recipe_id", "recipes"),
    "recipes_to_tags": ("recipe_id", "recipes"),
    "recipes_to_tools": ("recipe_id", "recipes"),
    "recipe_assets": ("recipe_id", "recipes"),
    "recipe_settings": ("recipe_id", "recipes"),
    "recipe_nutrition": ("recipe_id", "recipes"),
    "recipe_instructions": ("recipe_id", "recipes"),
    "recipe_ingredient_ref_link": ("instruction_id", "recipe_instructions"),
    "recipe_note_ref_link": ("instruction_id", "recipe_instructions"),
    "recipes_ingredients": ("recipe_id", "recipes"),
    "recipes_ingredients_substitutions": ("ingredient_id", "recipes_ingredients"),
    "recipe_comments": ("recipe_id", "recipes"),
    "recipe_timeline_events": ("recipe_id", "recipes"),
    "notes": ("recipe_id", "recipes"),
    "api_extras": ("recipee_id", "recipes"),
    "ingredient_units_aliases": ("unit_id", "ingredient_units"),
    "ingredient_foods_aliases": ("food_id", "ingredient_foods"),
    "ingredient_foods_substitutions": ("food_id", "ingredient_foods"),
    "ingredient_food_extras": ("ingredient_food_id", "ingredient_foods"),
    "users_to_recipes": ("recipe_id", "recipes"),
}
# Reverse relationships also remove dependent association rows. These alternate
# edges never delete the referenced recipe, household, list, category or food.
_ALTERNATE_OWNERS: dict[str, tuple[str, str]] = {
    "recipe_share_tokens": ("recipe_id", "recipes"),
    "group_to_categories": ("category_id", "categories"),
    "recipes_to_categories": ("category_id", "categories"),
    "recipes_to_tags": ("tag_id", "tags"),
    "recipes_to_tools": ("tool_id", "tools"),
    "ingredient_foods_substitutions": ("substitute_food_id", "ingredient_foods"),
    "recipes_ingredients_substitutions": ("substitute_food_id", "ingredient_foods"),
}
_NULL_REFERENCES = (
    ("recipes_ingredients", "referenced_recipe_id", "recipes"),
    ("recipes_ingredients", "food_id", "ingredient_foods"),
    ("recipes_ingredients", "unit_id", "ingredient_units"),
    ("ingredient_foods", "label_id", "multi_purpose_labels"),
    ("users", "owned_recipes_id", "recipes"),
)
_NATIVE_TABLES = {
    "ai_provider_headers",
    "ai_provider_params",
    "ai_provider_settings",
    "ai_providers",
    "cookbooks",
    "group_data_exports",
    "group_events_notifier_options",
    "group_events_notifiers",
    "group_meal_plan_rules",
    "group_meal_plans",
    "group_preferences",
    "group_reports",
    "groups",
    "household_preferences",
    "households",
    "households_to_recipes",
    "invite_tokens",
    "long_live_tokens",
    "password_reset_tokens",
    "plan_rules_to_households",
    "recipe_actions",
    "report_entries",
    "server_tasks",
    "shopping_list_extras",
    "shopping_list_item_extras",
    "shopping_list_item_recipe_reference",
    "shopping_list_items",
    "shopping_list_recipe_reference",
    "shopping_lists",
    "shopping_lists_multi_purpose_labels",
    "users",
    "webhook_urls",
}


async def _execute(connection: BaseDBAsyncClient, sql: str, values: list[Any]) -> None:
    postgres = connection.capabilities.dialect == "postgres"
    if postgres:
        parts = sql.split("?")
        sql = "".join(part + (f"${i + 1}" if i < len(parts) - 1 else "") for i, part in enumerate(parts))
    parameters = [
        (str(value) if postgres else value.hex)
        if isinstance(value, UUID)
        else value.astimezone(UTC).replace(tzinfo=None)
        if isinstance(value, datetime)
        else value
        for value in values
    ]
    await connection.execute_query(sql, parameters)


async def delete_group_dependents(group_id: UUID, using_db: BaseDBAsyncClient) -> None:
    """Preserve deletion restrictions and cascades on the caller's transaction."""
    if await User.filter(group_id=group_id).using_db(using_db).exists():
        raise IntegrityError("Cannot delete group with users")

    await ServerTaskModel.filter(group_id=group_id).using_db(using_db).delete()
    reports = await ReportModel.filter(group_id=group_id).using_db(using_db).values_list("id", flat=True)
    await ReportEntryModel.filter(report_id__in=reports).using_db(using_db).delete()
    await ReportModel.filter(group_id=group_id).using_db(using_db).delete()
    settings = await AIProviderSettings.filter(group_id=group_id).using_db(using_db).values_list("id", flat=True)
    providers = await AIProvider.filter(settings_id__in=settings).using_db(using_db).values_list("id", flat=True)
    for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
        await (
            AIProviderSettings.filter(**{f"{field}__in": providers})
            .using_db(using_db)
            .update(**{field: None, "update_at": datetime.now(UTC)})
        )
    await AIProviderHeaders.filter(provider_id__in=providers).using_db(using_db).delete()
    await AIProviderParams.filter(provider_id__in=providers).using_db(using_db).delete()
    await AIProvider.filter(id__in=providers).using_db(using_db).delete()
    await AIProviderSettings.filter(group_id=group_id).using_db(using_db).delete()
    await GroupPreferencesModel.filter(group_id=group_id).using_db(using_db).delete()
    await GroupDataExportsModel.filter(group_id=group_id).using_db(using_db).delete()

    from mealie.repos._household_coexistence import clear_recipe_domain_references, delete_group_household_dependents

    await delete_group_household_dependents(group_id, using_db)
    postgres = using_db.capabilities.dialect == "postgres"
    recipe_identifiers: dict[str, list[Any]] = {}
    for table_name in ("recipes", "ingredient_foods", "ingredient_units", "multi_purpose_labels"):
        rows = await using_db.execute_query_dict(
            f'SELECT id FROM "{table_name}" WHERE group_id = {"$1" if postgres else "?"}',
            [str(group_id) if postgres else group_id.hex],
        )
        recipe_identifiers[table_name] = [row["id"] for row in rows]
    await clear_recipe_domain_references(recipe_identifiers, using_db)

    metadata = SqlAlchemyBase.metadata
    owned = {
        name: table
        for name, table in metadata.tables.items()
        if name not in _NATIVE_TABLES and ("group_id" in table.c or name in _OWNERS)
    }

    def condition(table_name: str) -> str:
        conditions = []
        if "group_id" in owned[table_name].c:
            conditions.append('"group_id" = ?')
        else:
            column, parent = _OWNERS[table_name]
            conditions.append(f'"{column}" IN (SELECT id FROM "{parent}" WHERE {condition(parent)})')
        if table_name in _ALTERNATE_OWNERS:
            column, parent = _ALTERNATE_OWNERS[table_name]
            conditions.append(f'"{column}" IN (SELECT id FROM "{parent}" WHERE {condition(parent)})')
        return "(" + " OR ".join(conditions) + ")"

    # Retain referring objects in other groups and clear only nullable pointers,
    # as the legacy ORM did when deleting recipes, foods, units and households.
    for table, column, parent in _NULL_REFERENCES:
        predicate = condition(parent)
        await _execute(
            using_db,
            f'UPDATE "{table}" SET "{column}" = NULL, update_at = ? '
            f'WHERE "{column}" IN (SELECT id FROM "{parent}" WHERE {predicate})',
            [datetime.now(UTC), *([group_id] * predicate.count("?"))],
        )
    for owned_table in reversed(sort_tables(owned.values())):
        predicate = condition(owned_table.name)
        await _execute(
            using_db,
            f'DELETE FROM "{owned_table.name}" WHERE {predicate}',
            [group_id] * predicate.count("?"),
        )
