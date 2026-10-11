"""Native backup cycles, validation and atomic replacement regressions."""

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from tortoise.exceptions import IntegrityError

from mealie.core.config import get_app_settings
from mealie.core.settings.db_providers import SQLiteProvider
from mealie.db.init_db import prepare_database
from mealie.db.models.group.ai_providers import AIProvider, AIProviderSettings
from mealie.db.models.group.group import Group
from mealie.db.models.household.household import Household
from mealie.db.models.recipe.ingredient import (
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    RecipeIngredientModel,
    RecipeIngredientSubstitutionModel,
)
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.users.users import User
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.services.backups_v2.tortoise_exporter import BackupSchemaMismatch, TortoiseExporter


@pytest.mark.asyncio
async def test_native_backup_restores_cycles_and_rolls_back_invalid_references(tmp_path: Path) -> None:
    settings = get_app_settings().model_copy(update={"DB_PROVIDER": SQLiteProvider(data_dir=tmp_path)})
    async with database_context(get_tortoise_config(settings)) as context:
        await prepare_database()
        group = await Group.create(name="backup", slug="backup")
        household = await Household.create(name="backup", slug="backup", group_id=group.id)
        user = await User.create(
            username="backup", email="backup@example.com", password="hash", group_id=group.id, household_id=household.id
        )
        recipe = await RecipeModel.create(name="Backup recipe", group_id=group.id, user_id=user.id)
        user.owned_recipes_id = recipe.id
        await user.save(update_fields=["owned_recipes_id"])
        provider_settings = await AIProviderSettings.create(group_id=group.id)
        provider = await AIProvider.create(
            settings_id=provider_settings.id, name="backup", api_key="key", model="model"
        )
        provider_settings.default_provider_id = provider.id
        provider_settings.audio_provider_id = provider.id
        provider_settings.image_provider_id = provider.id
        await provider_settings.save(update_fields=["default_provider_id", "audio_provider_id", "image_provider_id"])
        food = await IngredientFoodModel.create(name="food", group_id=group.id)
        substitute = await IngredientFoodModel.create(name="substitute", group_id=group.id)
        await IngredientFoodSubstitutionModel.create(food_id=food.id, substitute_food_id=substitute.id, note=None)
        ingredient = await RecipeIngredientModel.create(recipe_id=recipe.id, food_id=food.id)
        await RecipeIngredientSubstitutionModel.create(
            ingredient_id=ingredient.id, substitute_food_id=substitute.id, note=None
        )

        exporter = TortoiseExporter()
        snapshot = await exporter.dump()
        await exporter.restore(snapshot)
        assert await exporter.dump() == snapshot
        assert (await User.get(id=user.id)).owned_recipes_id == recipe.id
        restored_settings = await AIProviderSettings.get(id=provider_settings.id)
        assert restored_settings.default_provider_id == provider.id
        assert restored_settings.audio_provider_id == provider.id
        assert restored_settings.image_provider_id == provider.id
        assert await IngredientFoodSubstitutionModel.filter(substitute_food_id=substitute.id, note=None).count() == 1
        assert await RecipeIngredientSubstitutionModel.filter(substitute_food_id=substitute.id, note=None).count() == 1
        assert (await context.db().execute_query_dict("PRAGMA foreign_keys"))[0]["foreign_keys"] == 1

        invalid = deepcopy(snapshot)
        invalid["recipes"][0]["user_id"] = uuid4().hex
        with pytest.raises(IntegrityError):
            await exporter.restore(invalid)
        assert await exporter.dump() == snapshot
        assert (await context.db().execute_query_dict("PRAGMA foreign_key_check")) == []

        mismatched = deepcopy(snapshot)
        mismatched["aerich"][0]["version"] = "unrecognized-schema"
        with pytest.raises(BackupSchemaMismatch):
            await exporter.restore(mismatched)
        assert await exporter.dump() == snapshot
