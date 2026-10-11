"""Native recipe hydration shared by household repositories."""

from typing import Any
from uuid import UUID

from mealie.db.models.recipe.ingredient import IngredientFoodModel, IngredientUnitModel
from mealie.db.models.recipe.labels import MultiPurposeLabel
from mealie.db.models.recipe.recipe import RecipeModel


async def recipe_summary(recipe_id: UUID | str | None) -> dict[str, Any] | None:
    if recipe_id is None:
        return None
    from ._recipe_persistence import recipe_data

    recipe = await RecipeModel.get_or_none(id=recipe_id)
    return await recipe_data(recipe, summary=True) if recipe else None


async def label(label_id: UUID | str | None) -> dict[str, Any] | None:
    if label_id is None:
        return None
    from .repository_recipe_base import hydrate_recipe_entity

    entry = await MultiPurposeLabel.get_or_none(id=label_id)
    return await hydrate_recipe_entity(entry) if entry else None


async def ingredient_unit(unit_id: UUID | str | None) -> dict[str, Any] | None:
    if unit_id is None:
        return None
    from .repository_recipe_base import hydrate_recipe_entity

    entry = await IngredientUnitModel.get_or_none(id=unit_id)
    return await hydrate_recipe_entity(entry) if entry else None


async def ingredient_food(food_id: UUID | str | None) -> dict[str, Any] | None:
    if food_id is None:
        return None
    from .repository_recipe_base import hydrate_recipe_entity

    entry = await IngredientFoodModel.get_or_none(id=food_id)
    return await hydrate_recipe_entity(entry) if entry else None
