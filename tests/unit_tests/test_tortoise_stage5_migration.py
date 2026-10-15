from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from aerich import Command
from tortoise import Tortoise
from tortoise.exceptions import IntegrityError

from mealie.db.tortoise_models import (
    AIProvider,
    AIProviderSettings,
    Category,
    CookBook,
    Group,
    GroupMealPlanRules,
    Household,
    HouseholdToRecipe,
    IngredientFood,
    MultiPurposeLabel,
    Recipe,
    ShoppingList,
    ShoppingListItem,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
    Tag,
    Tool,
    User,
    UserToRecipe,
)
from mealie.db.tortoise_setup import tortoise_config

_ROOT = Path(__file__).parents[2]
_MIGRATION_DIR = _ROOT / "mealie" / "db" / "aerich_migrations" / "models"
_STAGE4_MIGRATION = _MIGRATION_DIR / "1_stage4_recipe_constraints.py"
_STAGE5_MIGRATION = _MIGRATION_DIR / "2_stage5_cross_domain_foreign_keys.py"

_KEYLESS_ASSOCIATIONS = {
    "group_to_categories": ("group_id", "category_id"),
    "plan_rules_to_categories": ("group_plan_rule_id", "category_id"),
    "recipes_to_categories": ("recipe_id", "category_id"),
    "cookbooks_to_categories": ("cookbook_id", "category_id"),
    "recipes_to_tags": ("recipe_id", "tag_id"),
    "plan_rules_to_tags": ("plan_rule_id", "tag_id"),
    "cookbooks_to_tags": ("cookbook_id", "tag_id"),
    "households_to_tools": ("household_id", "tool_id"),
    "recipes_to_tools": ("recipe_id", "tool_id"),
    "cookbooks_to_tools": ("cookbook_id", "tool_id"),
    "plan_rules_to_households": ("group_plan_rule_id", "household_id"),
    "households_to_ingredient_foods": ("household_id", "food_id"),
}

_KEYLESS_FOREIGN_KEYS = {
    "group_to_categories": {"group_id": "groups", "category_id": "categories"},
    "plan_rules_to_categories": {
        "group_plan_rule_id": "group_meal_plan_rules",
        "category_id": "categories",
    },
    "recipes_to_categories": {"recipe_id": "recipes", "category_id": "categories"},
    "cookbooks_to_categories": {"cookbook_id": "cookbooks", "category_id": "categories"},
    "recipes_to_tags": {"recipe_id": "recipes", "tag_id": "tags"},
    "plan_rules_to_tags": {"plan_rule_id": "group_meal_plan_rules", "tag_id": "tags"},
    "cookbooks_to_tags": {"cookbook_id": "cookbooks", "tag_id": "tags"},
    "households_to_tools": {"household_id": "households", "tool_id": "tools"},
    "recipes_to_tools": {"recipe_id": "recipes", "tool_id": "tools"},
    "cookbooks_to_tools": {"cookbook_id": "cookbooks", "tool_id": "tools"},
    "plan_rules_to_households": {
        "group_plan_rule_id": "group_meal_plan_rules",
        "household_id": "households",
    },
    "households_to_ingredient_foods": {
        "household_id": "households",
        "food_id": "ingredient_foods",
    },
}

_COMPOSITE_KEYS = {
    "households_to_recipes": ("id", "household_id", "recipe_id"),
    "shopping_list_item_recipe_reference": ("id", "shopping_list_item_id"),
    "shopping_list_recipe_reference": ("id", "shopping_list_id"),
    "shopping_lists_multi_purpose_labels": ("id", "shopping_list_id", "label_id"),
    "users_to_recipes": ("id", "user_id", "recipe_id"),
}

_STAGE5_FOREIGN_KEYS = {
    "ai_provider_settings": {
        "default_provider_id": "ai_providers",
        "audio_provider_id": "ai_providers",
        "image_provider_id": "ai_providers",
    },
    "users": {"owned_recipes_id": "recipes"},
}


async def _table_rows(db, table: str) -> list[dict]:
    return await db.execute_query_dict(f'SELECT * FROM "{table}" ORDER BY rowid')


async def _index_inventory(db, table: str) -> tuple:
    indexes = await db.execute_query_dict(f'PRAGMA index_list("{table}")')
    inventory = []
    for index in indexes:
        columns = await db.execute_query_dict(f'PRAGMA index_info("{index["name"]}")')
        sql = await db.execute_query_dict(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", [index["name"]]
        )
        inventory.append(
            (index["name"], index["unique"], tuple(row["name"] for row in columns), sql[0]["sql"])
        )
    return tuple(sorted(inventory))


async def _foreign_key_inventory(db, table: str) -> dict[str, tuple[str, str, str]]:
    rows = await db.execute_query_dict(f'PRAGMA foreign_key_list("{table}")')
    return {row["from"]: (row["table"], row["to"], row["on_delete"]) for row in rows}


async def _assert_unique_tuple(db, table: str, expected_columns: tuple[str, ...]) -> None:
    indexes = await db.execute_query_dict(f'PRAGMA index_list("{table}")')
    unique_tuples = set()
    for index in indexes:
        if index["unique"]:
            columns = await db.execute_query_dict(f'PRAGMA index_info("{index["name"]}")')
            unique_tuples.add(tuple(row["name"] for row in columns))
    assert expected_columns in unique_tuples


async def _unique_tuples(db, table: str) -> set[tuple[str, ...]]:
    indexes = await db.execute_query_dict(f'PRAGMA index_list("{table}")')
    unique_tuples = set()
    for index in indexes:
        if index["unique"]:
            columns = await db.execute_query_dict(f'PRAGMA index_info("{index["name"]}")')
            unique_tuples.add(tuple(row["name"] for row in columns))
    return unique_tuples


@pytest.mark.asyncio
async def test_stage5_ordered_aerich_migrations_preserve_schema_and_key_behavior():
    with TemporaryDirectory(prefix="mealie-stage5-aerich-") as tmp:
        root = Path(tmp)
        db_path = root / "stage5.sqlite3"
        migrations = root / "migrations"
        command = Command(
            tortoise_config=tortoise_config(f"sqlite://{db_path}"),
            app="models",
            location=str(migrations),
        )
        try:
            await command.init_db(safe=True)
            await command.init()
            db = Tortoise.get_connection("default")

            group = await Group.create(name="Stage 5")
            household = await Household.create(name="home", group=group)
            other_household = await Household.create(name="other home", group=group)
            user = await User.create(group=group, full_name="Owner")
            other_user = await User.create(group=group, full_name="Other")
            recipe = await Recipe.create(
                group=group,
                name="recipe",
                name_normalized="recipe",
                user=user,
            )
            other_recipe = await Recipe.create(
                group=group,
                name="other recipe",
                name_normalized="other recipe",
                user=other_user,
            )

            settings = await AIProviderSettings.create(group=group)
            provider = await AIProvider.create(
                settings=settings,
                name="provider",
                api_key="key",
                model="model",
            )
            settings.default_provider = provider
            settings.audio_provider = provider
            settings.image_provider = provider
            await settings.save()
            user.owned_recipes = recipe
            await user.save()

            shopping_list = await ShoppingList.create(group=group, user=user, name="list")
            other_list = await ShoppingList.create(group=group, user=other_user, name="other list")
            item = await ShoppingListItem.create(shopping_list=shopping_list, position=0)
            other_item = await ShoppingListItem.create(shopping_list=other_list, position=0)
            label = await MultiPurposeLabel.create(group=group, name="label")
            category = await Category.create(group=group, name="category", slug="category")
            tag = await Tag.create(group=group, name="tag", slug="tag")
            tool = await Tool.create(group=group, name="tool", slug="tool")
            cookbook = await CookBook.create(
                group=group,
                household=household,
                name="cookbook",
                slug="cookbook",
            )
            plan_rule = await GroupMealPlanRules.create(group=group, household=household)
            food = await IngredientFood.create(group=group, name="food")

            keyless_values = {
                "group_to_categories": ("group_id", str(group.id), "category_id", str(category.id)),
                "plan_rules_to_categories": (
                    "group_plan_rule_id", str(plan_rule.id), "category_id", str(category.id)
                ),
                "recipes_to_categories": ("recipe_id", str(recipe.id), "category_id", str(category.id)),
                "cookbooks_to_categories": (
                    "cookbook_id", str(cookbook.id), "category_id", str(category.id)
                ),
                "recipes_to_tags": ("recipe_id", str(recipe.id), "tag_id", str(tag.id)),
                "plan_rules_to_tags": ("plan_rule_id", str(plan_rule.id), "tag_id", str(tag.id)),
                "cookbooks_to_tags": ("cookbook_id", str(cookbook.id), "tag_id", str(tag.id)),
                "households_to_tools": ("household_id", str(household.id), "tool_id", str(tool.id)),
                "recipes_to_tools": ("recipe_id", str(recipe.id), "tool_id", str(tool.id)),
                "cookbooks_to_tools": ("cookbook_id", str(cookbook.id), "tool_id", str(tool.id)),
                "plan_rules_to_households": (
                    "group_plan_rule_id", str(plan_rule.id), "household_id", str(household.id)
                ),
                "households_to_ingredient_foods": (
                    "household_id", str(household.id), "food_id", str(food.id)
                ),
            }

            # SQL UNIQUE permits repeated rows when one or more key columns are NULL.
            for table, pair in _KEYLESS_ASSOCIATIONS.items():
                first, second = pair
                await db.execute_query(
                    f'INSERT INTO "{table}" ("{first}", "{second}") VALUES (NULL, NULL)'
                )
                first_col, first_id, second_col, second_id = keyless_values[table]
                await db.execute_query(
                    f'INSERT INTO "{table}" ("{first_col}", "{second_col}") VALUES (?, ?)',
                    [first_id, second_id],
                )
                await db.execute_query(
                    f'INSERT INTO "{table}" ("{first}", "{second}") VALUES (NULL, NULL)'
                )

            shared_id = uuid4()
            household_rows = [
                await HouseholdToRecipe.create(
                    id=shared_id, household=household, recipe=recipe, last_made=None
                ),
                await HouseholdToRecipe.create(
                    id=shared_id, household=other_household, recipe=other_recipe, last_made=None
                ),
            ]
            with pytest.raises(IntegrityError):
                await HouseholdToRecipe.create(id=shared_id, household=household, recipe=recipe)

            item_ref_rows = [
                await ShoppingListItemRecipeReference.create(
                    id=shared_id, shopping_list_item=item, recipe=recipe, recipe_quantity=1
                ),
                await ShoppingListItemRecipeReference.create(
                    id=shared_id, shopping_list_item=other_item, recipe=other_recipe, recipe_quantity=2
                ),
            ]
            assert item_ref_rows[0].recipe_scale == 1
            with pytest.raises(IntegrityError):
                await ShoppingListItemRecipeReference.create(
                    id=shared_id, shopping_list_item=item, recipe_quantity=3
                )

            list_ref_rows = [
                await ShoppingListRecipeReference.create(
                    id=shared_id, shopping_list=shopping_list, recipe=recipe, recipe_quantity=1
                ),
                await ShoppingListRecipeReference.create(
                    id=shared_id, shopping_list=other_list, recipe=other_recipe, recipe_quantity=2
                ),
            ]
            with pytest.raises(IntegrityError):
                await ShoppingListRecipeReference.create(
                    id=shared_id, shopping_list=shopping_list, recipe_quantity=3
                )

            label_rows = [
                await ShoppingListMultiPurposeLabel.create(
                    id=shared_id, shopping_list=shopping_list, label=label
                ),
                await ShoppingListMultiPurposeLabel.create(
                    id=shared_id, shopping_list=other_list, label=label
                ),
            ]
            assert label_rows[0].position == 0
            with pytest.raises(IntegrityError):
                await ShoppingListMultiPurposeLabel.create(
                    id=uuid4(), shopping_list=shopping_list, label=label
                )

            rating_rows = [
                await UserToRecipe.create(id=shared_id, user=user, recipe=recipe, is_favorite=True),
                await UserToRecipe.create(id=shared_id, user=other_user, recipe=other_recipe, is_favorite=False),
            ]
            with pytest.raises(IntegrityError):
                await UserToRecipe.create(id=shared_id, user=user, recipe=recipe, is_favorite=False)
            assert rating_rows[0].rating is None

            # Existing Stage 5 relations load before and after constraints are installed.
            await settings.fetch_related("default_provider", "audio_provider", "image_provider")
            assert settings.default_provider.id == provider.id
            assert settings.audio_provider.id == provider.id
            assert settings.image_provider.id == provider.id
            await user.fetch_related("owned_recipes")
            assert user.owned_recipes.id == recipe.id

            # Preserve schema/data snapshots across the ordered migrations.
            watched_tables = (
                "ai_provider_settings",
                "users",
                *tuple(_COMPOSITE_KEYS),
                *tuple(_KEYLESS_ASSOCIATIONS),
            )
            before_rows = {table: await _table_rows(db, table) for table in watched_tables}
            before_indexes = {
                table: await _index_inventory(db, table)
                for table in ("ai_provider_settings", "users")
            }
            before_foreign_keys = {
                table: await _foreign_key_inventory(db, table) for table in _STAGE5_FOREIGN_KEYS
            }
            shutil.copy2(_STAGE4_MIGRATION, migrations / "models" / _STAGE4_MIGRATION.name)
            shutil.copy2(_STAGE5_MIGRATION, migrations / "models" / _STAGE5_MIGRATION.name)
            assert await command.upgrade(run_in_transaction=False) == [
                _STAGE4_MIGRATION.name,
                _STAGE5_MIGRATION.name,
            ]

            migrated_rows = {table: await _table_rows(db, table) for table in watched_tables}
            assert migrated_rows == before_rows
            for table, snapshot in before_indexes.items():
                assert await _index_inventory(db, table) == snapshot

            for table, columns in _STAGE5_FOREIGN_KEYS.items():
                observed = await _foreign_key_inventory(db, table)
                expected = dict(before_foreign_keys[table])
                for column, target in columns.items():
                    assert observed[column] == (target, "id", "NO ACTION")
                    expected[column] = (target, "id", "NO ACTION")
                assert observed == expected
            assert (await db.execute_query_dict("PRAGMA foreign_keys"))[0]["foreign_keys"] == 1
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []
            await settings.fetch_related("default_provider", "audio_provider", "image_provider")
            assert settings.default_provider.id == provider.id
            assert settings.audio_provider.id == provider.id
            assert settings.image_provider.id == provider.id
            await user.fetch_related("owned_recipes")
            assert user.owned_recipes.id == recipe.id
            for table, constraints in _STAGE5_FOREIGN_KEYS.items():
                for column in constraints:
                    with pytest.raises(IntegrityError):
                        await db.execute_query(
                            f'UPDATE "{table}" SET "{column}"=? WHERE "id"=?',
                            [str(uuid4()), str(settings.id if table == "ai_provider_settings" else user.id)],
                        )
            settings.default_provider = None
            settings.audio_provider = None
            settings.image_provider = None
            await settings.save()
            user.owned_recipes = None
            await user.save()
            await settings.fetch_related("default_provider", "audio_provider", "image_provider")
            await user.fetch_related("owned_recipes")
            assert settings.default_provider is None
            assert settings.audio_provider is None
            assert settings.image_provider is None
            assert user.owned_recipes is None
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []

            # Each keyless association keeps its exact former FK/unique pair and SQL NULL behavior.
            for table, pair in _KEYLESS_ASSOCIATIONS.items():
                row_id = await db.execute_query_dict(f'PRAGMA table_info("{table}")')
                surrogate = "id" if table == "households_to_ingredient_foods" else "row_id"
                assert next(row for row in row_id if row["name"] == surrogate)["pk"] == 1
                await _assert_unique_tuple(db, table, pair)
                assert await _unique_tuples(db, table) == {pair}
                observed = await _foreign_key_inventory(db, table)
                for column, target in _KEYLESS_FOREIGN_KEYS[table].items():
                    assert observed[column] == (target, "id", "NO ACTION")
                    with pytest.raises(IntegrityError):
                        await db.execute_query(
                            f'INSERT INTO "{table}" ("{column}") VALUES (?)', [str(uuid4())]
                        )
                null_count = await db.execute_query_dict(
                    f'SELECT COUNT(*) AS count FROM "{table}" WHERE "{pair[0]}" IS NULL AND "{pair[1]}" IS NULL'
                )
                assert null_count[0]["count"] == 2
                duplicate_rows = await db.execute_query_dict(
                    f'SELECT "{surrogate}" FROM "{table}" '
                    f'WHERE "{pair[0]}" IS NULL AND "{pair[1]}" IS NULL ORDER BY "{surrogate}"'
                )
                first_key, second_key = (row[surrogate] for row in duplicate_rows)
                moved_key = max(first_key, second_key) + 1000
                await db.execute_query(
                    f'UPDATE "{table}" SET "{surrogate}"=? WHERE "{surrogate}"=?',
                    [moved_key, first_key],
                )
                assert await db.execute_query_dict(
                    f'SELECT "{surrogate}" FROM "{table}" WHERE "{surrogate}"=?', [moved_key]
                ) == [{surrogate: moved_key}]
                assert await db.execute_query_dict(
                    f'SELECT "{surrogate}" FROM "{table}" WHERE "{surrogate}"=?', [second_key]
                ) == [{surrogate: second_key}]
                await db.execute_query(
                    f'DELETE FROM "{table}" WHERE "{surrogate}"=?', [moved_key]
                )
                assert await db.execute_query_dict(
                    f'SELECT "{surrogate}" FROM "{table}" WHERE "{surrogate}"=?', [moved_key]
                ) == []
                remaining_null_count = await db.execute_query_dict(
                    f'SELECT COUNT(*) AS count FROM "{table}" '
                    f'WHERE "{pair[0]}" IS NULL AND "{pair[1]}" IS NULL'
                )
                assert remaining_null_count[0]["count"] == 1
                first_col, first_id, second_col, second_id = keyless_values[table]
                with pytest.raises(IntegrityError):
                    await db.execute_query(
                        f'INSERT INTO "{table}" ("{first_col}", "{second_col}") VALUES (?, ?)',
                        [first_id, second_id],
                    )

            # Former composite tuples remain unique; id alone is no longer over-constrained.
            for table, pair in _COMPOSITE_KEYS.items():
                await _assert_unique_tuple(db, table, pair)
                expected_uniques = {pair}
                if table in {"households_to_recipes", "shopping_lists_multi_purpose_labels", "users_to_recipes"}:
                    expected_uniques.add(
                        {
                            "households_to_recipes": ("household_id", "recipe_id"),
                            "shopping_lists_multi_purpose_labels": ("shopping_list_id", "label_id"),
                            "users_to_recipes": ("user_id", "recipe_id"),
                        }[table]
                    )
                assert await _unique_tuples(db, table) == expected_uniques
                info = await db.execute_query_dict(f'PRAGMA table_info("{table}")')
                assert next(row for row in info if row["name"] == "row_id")["pk"] == 1
                assert next(row for row in info if row["name"] == "id")["pk"] == 0

            # Row-scoped updates/deletes use the surrogate, even when UUID id values repeat.
            for row in (household_rows, item_ref_rows, list_ref_rows, label_rows, rating_rows):
                assert row[0].row_id != row[1].row_id
                row[0].id = shared_id
                await row[0].save()
                await row[0].delete()
                assert await row[1].__class__.filter(pk=row[1].row_id).exists()

            upgraded_rows = {table: await _table_rows(db, table) for table in watched_tables}

            assert await command.downgrade(version=-1, delete=False) == [_STAGE5_MIGRATION.name]
            for table, columns in _STAGE5_FOREIGN_KEYS.items():
                observed = await _foreign_key_inventory(db, table)
                assert observed == before_foreign_keys[table]
            assert (await db.execute_query_dict("PRAGMA foreign_keys"))[0]["foreign_keys"] == 1
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []
            for table, snapshot in before_indexes.items():
                assert await _index_inventory(db, table) == snapshot
            for table in watched_tables:
                assert await _table_rows(db, table) == upgraded_rows[table]

            assert await command.downgrade(version=-1, delete=False) == [_STAGE4_MIGRATION.name]
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []
            for table in watched_tables:
                assert await _table_rows(db, table) == upgraded_rows[table]
        finally:
            await command.aclose()
