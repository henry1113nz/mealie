from collections.abc import Iterable
from typing import cast
from uuid import UUID

from pydantic import UUID4, BaseModel
from slugify import slugify
from tortoise.exceptions import IntegrityError
from tortoise.models import Model

from mealie.db.models.household import Household, HouseholdToRecipe
from mealie.db.models.recipe.category import Category
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.tag import Tag
from mealie.db.models.recipe.tool import Tool
from mealie.db.models.users.users import User
from mealie.repos.repository_generic import GroupRepositoryGeneric, HouseholdRepositoryGeneric
from mealie.schema.household import (
    HouseholdInDB,
    HouseholdRecipeOut,
    HouseholdStatistics,
)


class RepositoryHousehold(GroupRepositoryGeneric[HouseholdInDB, Household]):
    async def create(self, data: BaseModel | dict) -> HouseholdInDB:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        if not data.get("group_id"):
            data["group_id"] = self.group_id
        max_attempts = 10
        original_name = cast(str, data["name"])

        attempts = 0
        while True:
            try:
                data["slug"] = slugify(data["name"])
                return await super().create(data)
            except IntegrityError:
                attempts += 1
                if attempts >= max_attempts:
                    raise

                data["name"] = f"{original_name} ({attempts})"

    async def create_many(self, data: Iterable[BaseModel | dict]) -> list[HouseholdInDB]:
        # since create uses special logic for resolving slugs, we don't want to use the standard create_many method
        return [await self.create(new_household) for new_household in data]

    async def update(self, match_value: str | int | UUID4, new_data: BaseModel | dict) -> HouseholdInDB:
        if isinstance(new_data, BaseModel):
            new_data = new_data.model_dump()
        new_data["slug"] = slugify(new_data["name"])

        return await super().update(match_value, new_data)

    async def update_many(self, data: Iterable[BaseModel | dict]) -> list[HouseholdInDB]:
        # since update uses special logic for resolving slugs, we don't want to use the standard update_many method
        return [
            await self.update(
                household["id"] if isinstance(household, dict) else household.model_dump()["id"], household
            )
            for household in data
        ]

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

        if isinstance(slug_or_id, UUID):
            return await self.get_one(slug_or_id)
        else:
            return await self.get_one(slug_or_id, key="slug")

    async def statistics(self, group_id: UUID4, household_id: UUID4) -> HouseholdStatistics:
        async def model_count(model: type[Model], *, filter_household: bool = True) -> int:
            filters = {"group_id": group_id}
            if filter_household:
                filters["user__household_id" if model is RecipeModel else "household_id"] = household_id
            return await model.filter(**filters).using_db(self.session).count()

        return HouseholdStatistics(
            total_recipes=await model_count(RecipeModel),
            total_users=await model_count(User),
            total_categories=await model_count(Category, filter_household=False),
            total_tags=await model_count(Tag, filter_household=False),
            total_tools=await model_count(Tool, filter_household=False),
        )


class RepositoryHouseholdRecipes(HouseholdRepositoryGeneric[HouseholdRecipeOut, HouseholdToRecipe]):
    async def get_by_recipe(self, recipe_id: UUID4) -> HouseholdRecipeOut | None:
        if not self.household_id:
            raise Exception("household_id not set")

        return await self.get_one(recipe_id, key="recipe_id")
