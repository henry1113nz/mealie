from collections.abc import Iterable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from slugify import slugify
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from mealie.db.models.household import Household, HouseholdToRecipe
from mealie.db.models.users import User
from mealie.schema.household import HouseholdInDB, HouseholdRecipeOut, HouseholdStatistics

from .repository_household_base import AsyncHouseholdRepository


class RepositoryHousehold(AsyncHouseholdRepository[HouseholdInDB, Household]):
    async def create(self, data: BaseModel | dict[str, Any]) -> HouseholdInDB:
        values = data.copy() if isinstance(data, dict) else data.model_dump()
        if not values.get("group_id"):
            values["group_id"] = self.group_id
        original_name = values["name"]
        for attempt in range(10):
            values["name"] = f"{original_name} ({attempt})" if attempt else original_name
            values["slug"] = slugify(values["name"])
            try:
                return await super().create(values)
            except IntegrityError:
                if attempt == 9:
                    raise
        raise RuntimeError("Unreachable household creation attempt")

    async def create_many(self, data: Iterable[HouseholdInDB | dict[str, Any]]) -> list[HouseholdInDB]:
        async with in_transaction("default"):
            return [await self.create(household) for household in data]

    async def update(self, match_value: Any, new_data: BaseModel | dict[str, Any]) -> HouseholdInDB:
        values = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        values["slug"] = slugify(values["name"])
        return await super().update(match_value, values)

    async def get_by_name(self, name: str) -> HouseholdInDB | None:
        if not self.group_id:
            raise Exception("group_id not set")
        return await self.get_one(name, key="name")

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> HouseholdInDB | None:
        if isinstance(slug_or_id, str):
            try:
                slug_or_id = UUID(slug_or_id)
            except ValueError:
                pass
        return await self.get_one(slug_or_id, key="id" if isinstance(slug_or_id, UUID) else "slug")

    async def statistics(self, group_id: UUID, household_id: UUID) -> HouseholdStatistics:
        from mealie.db.models.recipe import Category, RecipeModel, Tag, Tool

        return HouseholdStatistics(
            total_recipes=await RecipeModel.filter(group_id=group_id, user__household_id=household_id).count(),
            total_users=await User.filter(group_id=group_id, household_id=household_id).count(),
            total_categories=await Category.filter(group_id=group_id).count(),
            total_tags=await Tag.filter(group_id=group_id).count(),
            total_tools=await Tool.filter(group_id=group_id).count(),
        )


class RepositoryHouseholdRecipes(AsyncHouseholdRepository[HouseholdRecipeOut, HouseholdToRecipe]):
    async def get_by_recipe(self, recipe_id: UUID) -> HouseholdRecipeOut | None:
        if not self.household_id:
            raise Exception("household_id not set")
        return await self.get_one(recipe_id, key="recipe_id")
