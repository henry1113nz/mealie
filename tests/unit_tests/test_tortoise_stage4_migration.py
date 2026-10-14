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
    Group,
    IngredientFood,
    IngredientFoodAlias,
    IngredientFoodSubstitution,
    IngredientUnit,
    IngredientUnitAlias,
    Recipe,
    RecipeIngredient,
    RecipeIngredientSubstitution,
)
from mealie.db.tortoise_setup import tortoise_config


@pytest.mark.asyncio
async def test_stage4_aerich_migration_constraints_alias_identity_and_downgrade():
    migration_source = (
        Path(__file__).parents[2] / "mealie" / "db" / "aerich_migrations" / "models"
        / "1_stage4_recipe_constraints.py"
    )
    with TemporaryDirectory(prefix="mealie-stage4-aerich-") as tmp:
        root = Path(tmp)
        db_path = root / "stage4.sqlite3"
        migrations = root / "migrations"
        config = tortoise_config(f"sqlite://{db_path}")
        command = Command(tortoise_config=config, app="models", location=str(migrations))
        try:
            # Aerich creates the initial schema and records its baseline version.
            await command.init_db(safe=True)
            await command.init()
            db = Tortoise.get_connection("default")
            group = await Group.create(name="Stage 4")
            food_a = await IngredientFood.create(group=group, name="food-a")
            food_b = await IngredientFood.create(group=group, name="food-b")
            unit_a = await IngredientUnit.create(group=group, name="unit-a")
            unit_b = await IngredientUnit.create(group=group, name="unit-b")
            recipe = await Recipe.create(group=group, name="recipe", name_normalized="recipe")
            ingredient = await RecipeIngredient.create(recipe=recipe, food=food_a, unit=unit_a, position=0)
            valid_food_sub = await IngredientFoodSubstitution.create(
                food=food_a, substitute_food=food_b, note=None
            )
            valid_note_sub = await RecipeIngredientSubstitution.create(
                ingredient=ingredient, substitute_food=None, note="use water"
            )
            alias_id = uuid4()
            alias_a = await IngredientFoodAlias.create(id=alias_id, food=food_a, name="alias-a")
            alias_b = await IngredientFoodAlias.create(id=alias_id, food=food_b, name="alias-b")
            unit_alias_id = uuid4()
            unit_alias_a = await IngredientUnitAlias.create(id=unit_alias_id, unit=unit_a, name="unit-alias-a")
            unit_alias_b = await IngredientUnitAlias.create(id=unit_alias_id, unit=unit_b, name="unit-alias-b")
            default_id_alias = await IngredientFoodAlias.create(food=food_a, name="default-id")
            assert default_id_alias.id is not None

            tables = (
                "ingredient_foods_substitutions",
                "recipes_ingredients_substitutions",
            )
            before_indexes = {
                table: {
                    row["name"]
                    for row in await db.execute_query_dict(f"PRAGMA index_list('{table}')")
                }
                for table in tables
            }
            stage4_migration = migrations / "models" / "1_stage4_recipe_constraints.py"
            shutil.copy2(migration_source, stage4_migration)
            assert await command.upgrade(run_in_transaction=False) == [stage4_migration.name]

            for table in tables:
                ddl = (
                    await db.execute_query_dict(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [table]
                    )
                )[0]["sql"]
                assert "CHECK" in ddl
                after_indexes = {
                    row["name"] for row in await db.execute_query_dict(f"PRAGMA index_list('{table}')")
                }
                assert after_indexes == before_indexes[table]
            assert await IngredientFoodSubstitution.filter(pk=valid_food_sub.pk).exists()
            assert await RecipeIngredientSubstitution.filter(pk=valid_note_sub.pk).exists()
            assert await IngredientFoodAlias.filter(pk=alias_a.pk).exists()
            assert await IngredientFoodAlias.filter(pk=alias_b.pk).exists()
            assert await IngredientUnitAlias.filter(pk=unit_alias_a.pk).exists()
            assert await IngredientUnitAlias.filter(pk=unit_alias_b.pk).exists()
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []

            for row in (
                {"food": food_a, "substitute_food": food_a, "note": "self"},
                {"food": food_a, "substitute_food": None, "note": None},
            ):
                with pytest.raises(IntegrityError):
                    await IngredientFoodSubstitution.create(**row)
            with pytest.raises(IntegrityError):
                await RecipeIngredientSubstitution.create(ingredient=ingredient, note=None)

            await RecipeIngredient.create(recipe=recipe, food=food_b, unit=unit_a, position=2)
            ordered_ingredients = await RecipeIngredient.filter(recipe=recipe).all()
            assert [row.position for row in ordered_ingredients] == [0, 2]
            await ordered_ingredients[0].fetch_related("food", "unit", "recipe")
            assert ordered_ingredients[0].food.name == "food-a"
            assert ordered_ingredients[0].unit.name == "unit-a"
            assert ordered_ingredients[0].recipe.id == recipe.id

            assert alias_a.pk != alias_b.pk
            with pytest.raises(IntegrityError):
                await IngredientFoodAlias.create(id=alias_id, food=food_a, name="duplicate-pair")

            found_a = await IngredientFoodAlias.get(id=alias_id, food=food_a)
            found_a.name = "updated-a"
            await found_a.save()
            assert (await IngredientFoodAlias.get(pk=alias_a.pk)).name == "updated-a"
            assert (await IngredientFoodAlias.get(pk=alias_b.pk)).name == "alias-b"
            await IngredientFoodAlias.filter(pk=alias_a.pk).delete()
            assert not await IngredientFoodAlias.filter(id=alias_id, food=food_a).exists()
            assert await IngredientFoodAlias.filter(id=alias_id, food=food_b).exists()

            assert unit_alias_a.pk != unit_alias_b.pk
            with pytest.raises(IntegrityError):
                await IngredientUnitAlias.create(id=unit_alias_id, unit=unit_a, name="duplicate-pair")
            found_unit_a = await IngredientUnitAlias.get(id=unit_alias_id, unit=unit_a)
            found_unit_a.name = "updated-unit-a"
            await found_unit_a.save()
            assert (await IngredientUnitAlias.get(pk=unit_alias_a.pk)).name == "updated-unit-a"
            assert (await IngredientUnitAlias.get(pk=unit_alias_b.pk)).name == "unit-alias-b"
            await IngredientUnitAlias.filter(pk=unit_alias_a.pk).delete()
            assert not await IngredientUnitAlias.filter(id=unit_alias_id, unit=unit_a).exists()
            assert await IngredientUnitAlias.filter(id=unit_alias_id, unit=unit_b).exists()

            alias_table = await db.execute_query_dict("PRAGMA table_info(ingredient_foods_aliases)")
            assert next(row for row in alias_table if row["name"] == "row_id")["pk"] == 1
            assert next(row for row in alias_table if row["name"] == "id")["pk"] == 0
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []

            assert await command.downgrade(version=-1, delete=False) == [stage4_migration.name]
            for table in tables:
                ddl = (await db.execute_query_dict(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", [table]
                ))[0]["sql"]
                assert "CHECK" not in ddl
                after_indexes = {
                    row["name"] for row in await db.execute_query_dict(f"PRAGMA index_list('{table}')")
                }
                assert after_indexes == before_indexes[table]
            assert await db.execute_query_dict("PRAGMA foreign_key_check") == []
            assert await IngredientFoodSubstitution.filter(pk=valid_food_sub.pk).exists()
            assert await RecipeIngredientSubstitution.filter(pk=valid_note_sub.pk).exists()
            assert await IngredientFoodSubstitution.create(
                food=food_a, substitute_food=food_a, note="invalid after downgrade"
            )
        finally:
            await command.aclose()
