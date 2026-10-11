from datetime import UTC, datetime

from pydantic import UUID4
from tortoise.transactions import in_transaction

from mealie.db.models.household.shopping_list import ShoppingListItem
from mealie.db.models.recipe.ingredient import (
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    RecipeIngredientModel,
    RecipeIngredientSubstitutionModel,
)
from mealie.schema.recipe.recipe_ingredient import IngredientFood

from .repository_recipe_base import AsyncRecipeRepository


class RepositoryFood(AsyncRecipeRepository[IngredientFood, IngredientFoodModel]):
    async def _get_food(self, id: UUID4) -> IngredientFoodModel:
        return await self._query_one(id)

    async def _merge_substitutions(self, from_model: IngredientFoodModel, to_model: IngredientFoodModel) -> None:
        to_food = to_model.id
        existing_substitute_ids = set(
            await IngredientFoodSubstitutionModel.filter(food_id=to_food)
            .exclude(substitute_food_id=None)
            .values_list("substitute_food_id", flat=True)
        )
        existing_source_ids = set(
            await IngredientFoodSubstitutionModel.filter(substitute_food_id=to_food).values_list("food_id", flat=True)
        )
        outbound = await IngredientFoodSubstitutionModel.filter(food_id=from_model.id).order_by("position")
        inbound = await IngredientFoodSubstitutionModel.filter(substitute_food_id=from_model.id).order_by("position")
        position = await IngredientFoodSubstitutionModel.filter(food_id=to_food).count()
        for row in outbound:
            if row.substitute_food_id is not None:
                if row.substitute_food_id == to_food or row.substitute_food_id in existing_substitute_ids:
                    continue
                existing_substitute_ids.add(row.substitute_food_id)
            row.food_id, row.position = to_food, position
            position += 1
            await row.save(update_fields=["food_id", "position", "update_at"])
        for row in inbound:
            if row.food_id == to_food or row.food_id in existing_source_ids:
                continue
            existing_source_ids.add(row.food_id)
            row.substitute_food_id = to_food
            await row.save(update_fields=["substitute_food_id", "update_at"])

    async def _merge_recipe_substitutions(self, from_food: UUID4, to_food: UUID4) -> None:
        rows = await RecipeIngredientSubstitutionModel.filter(substitute_food_id__in=[from_food, to_food]).order_by(
            "ingredient_id", "position"
        )
        repointed: set[int] = set()
        for row in rows:
            ingredient = await RecipeIngredientModel.get(id=row.ingredient_id)
            if ingredient.food_id in (from_food, to_food) or row.ingredient_id in repointed:
                await row.delete()
                continue
            repointed.add(row.ingredient_id)
            row.substitute_food_id = to_food
            await row.save(update_fields=["substitute_food_id", "update_at"])

    async def merge(self, from_food: UUID4, to_food: UUID4) -> IngredientFood | None:
        async with in_transaction("default"):
            from_model, to_model = await self._get_food(from_food), await self._get_food(to_food)
            if from_food == to_food:
                return await self.get_one(to_food)
            await self._merge_substitutions(from_model, to_model)
            await self._merge_recipe_substitutions(from_food, to_food)
            await RecipeIngredientModel.filter(food_id=from_food).update(food_id=to_food, update_at=datetime.now(UTC))
            await ShoppingListItem.filter(food_id=from_food).update(food_id=to_food, update_at=datetime.now(UTC))
            await from_model.delete()
            await self._after_write(from_model)
            return await self.get_one(to_food)
