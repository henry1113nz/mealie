from typing import cast

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

from .repository_generic import GroupRepositoryGeneric


class RepositoryFood(GroupRepositoryGeneric[IngredientFood, IngredientFoodModel]):
    async def _get_food(self, id: UUID4) -> IngredientFoodModel:
        return await self._query_one(id)

    async def merge(self, from_food: UUID4, to_food: UUID4) -> IngredientFood | None:
        # Resolve both through this repository before touching any rows: merges may
        # only cross foods in the caller's group.
        source = await self._get_food(from_food)
        await self._get_food(to_food)
        if from_food == to_food:
            return await self.get_one(to_food)
        async with in_transaction(self.session.connection_name) as connection:
            outbound = await IngredientFoodSubstitutionModel.filter(food_id=from_food).using_db(connection)
            inbound = await IngredientFoodSubstitutionModel.filter(substitute_food_id=from_food).using_db(connection)
            existing_substitutes = set(
                cast(
                    list[UUID4 | None],
                    await IngredientFoodSubstitutionModel.filter(food_id=to_food)
                    .using_db(connection)
                    .values_list("substitute_food_id", flat=True),
                )
            )
            existing_sources = set(
                cast(
                    list[UUID4],
                    await IngredientFoodSubstitutionModel.filter(substitute_food_id=to_food)
                    .using_db(connection)
                    .values_list("food_id", flat=True),
                )
            )
            for row in outbound:
                if row.substitute_food_id and (
                    row.substitute_food_id == to_food or row.substitute_food_id in existing_substitutes
                ):
                    continue
                existing_substitutes.add(row.substitute_food_id)
                row.food_id = to_food
                await row.save(using_db=connection)
            for row in inbound:
                if row.food_id in (from_food, to_food) or row.food_id in existing_sources:
                    continue
                existing_sources.add(row.food_id)
                row.substitute_food_id = to_food
                await row.save(using_db=connection)

            rows = (
                await RecipeIngredientSubstitutionModel.filter(substitute_food_id__in=[from_food, to_food])
                .using_db(connection)
                .select_related("ingredient")
                .order_by("ingredient_id", "position")
            )
            seen_ingredients: set[int] = set()
            for recipe_substitution in rows:
                if (
                    recipe_substitution.ingredient.food_id in (from_food, to_food)
                    or recipe_substitution.ingredient_id in seen_ingredients
                ):
                    await recipe_substitution.delete(using_db=connection)
                else:
                    seen_ingredients.add(recipe_substitution.ingredient_id)
                    recipe_substitution.substitute_food_id = to_food
                    await recipe_substitution.save(using_db=connection)
            await RecipeIngredientModel.filter(food_id=from_food).using_db(connection).update(food_id=to_food)
            await ShoppingListItem.filter(food_id=from_food).using_db(connection).update(food_id=to_food)
            await source.delete(using_db=connection)
        return await self.get_one(to_food)
