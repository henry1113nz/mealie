from functools import cached_property

from fastapi import HTTPException
from pydantic import UUID4

from mealie.repos.all_repositories import get_repositories
from mealie.routes._base import BaseUserController, controller
from mealie.routes._base.mixins import HttpRepo
from mealie.routes._base.routers import UserAPIRouter
from mealie.schema.recipe import RecipeShareTokenSummary
from mealie.schema.recipe.recipe_share_token import RecipeShareToken, RecipeShareTokenCreate, RecipeShareTokenSave

router = UserAPIRouter(prefix="/shared/recipes", tags=["Shared: Recipes"])


@controller(router)
class RecipeSharedController(BaseUserController):
    @cached_property
    def repo(self):
        return self.repos.recipe_share_tokens

    @cached_property
    def mixins(self):
        return HttpRepo[RecipeShareTokenSave, RecipeShareToken, RecipeShareTokenCreate](self.repo, self.logger)

    @router.get("", response_model=list[RecipeShareTokenSummary])
    async def get_all(self, recipe_id: UUID4 | None = None):
        if recipe_id:
            return await self.repo.multi_query({"recipe_id": recipe_id}, override_schema=RecipeShareTokenSummary)
        else:
            return await self.repo.get_all(override=RecipeShareTokenSummary)

    @router.post("", response_model=RecipeShareToken, status_code=201)
    async def create_one(self, data: RecipeShareTokenCreate) -> RecipeShareToken:
        # check if recipe group id is the same as the user group id
        group_repos = get_repositories(self.repos.session, group_id=self.group_id, household_id=None)
        recipe = await group_repos.recipes.get_one(data.recipe_id, "id")
        if recipe is None or recipe.group_id != self.group_id:
            raise HTTPException(status_code=404, detail="Recipe not found in your group")

        save_data = RecipeShareTokenSave(**data.model_dump(), group_id=self.group_id)
        return await self.mixins.create_one(save_data)

    @router.get("/{item_id}", response_model=RecipeShareToken)
    async def get_one(self, item_id: UUID4):
        return await self.mixins.get_one(item_id)

    @router.delete("/{item_id}")
    async def delete_one(self, item_id: UUID4) -> None:
        return await self.mixins.delete_one(item_id)
