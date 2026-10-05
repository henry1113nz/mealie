from functools import cached_property

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.routes._base.mixins import HttpRepo
from mealie.schema.recipe.recipe_comments import (
    RecipeCommentCreate,
    RecipeCommentOut,
    RecipeCommentPagination,
    RecipeCommentSave,
    RecipeCommentUpdate,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.responses import ErrorResponse, SuccessResponse

router = APIRouter(prefix="/comments", tags=["Recipe: Comments"])


@controller(router)
class RecipeCommentRoutes(BaseUserController):
    @cached_property
    def repo(self):
        return self.repos.comments

    # =======================================================================
    # CRUD Operations

    @property
    def mixins(self) -> HttpRepo:
        return HttpRepo(self.repo, self.logger, self.registered_exceptions, self.t("generic.server-error"))

    async def _check_comment_belongs_to_user(self, item_id: UUID4) -> None:
        comment = await self.repo.get_one(item_id)
        if comment.user_id != self.user.id and not self.user.admin:
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse(message="Comment does not belong to user"),
            )

    @router.get("", response_model=RecipeCommentPagination)
    async def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = await self.repo.page_all(
            pagination=q,
            override=RecipeCommentOut,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=RecipeCommentOut, status_code=201)
    async def create_one(self, data: RecipeCommentCreate):
        save_data = RecipeCommentSave(text=data.text, user_id=self.user.id, recipe_id=data.recipe_id)
        return await self.mixins.create_one(save_data)

    @router.get("/{item_id}", response_model=RecipeCommentOut)
    async def get_one(self, item_id: UUID4):
        return await self.mixins.get_one(item_id)

    @router.put("/{item_id}", response_model=RecipeCommentOut)
    async def update_one(self, item_id: UUID4, data: RecipeCommentUpdate):
        (await self._check_comment_belongs_to_user(item_id))
        return await self.mixins.update_one(data, item_id)

    @router.delete("/{item_id}", response_model=SuccessResponse)
    async def delete_one(self, item_id: UUID4):
        (await self._check_comment_belongs_to_user(item_id))
        (await self.mixins.delete_one(item_id))
        return SuccessResponse.respond(message="Comment deleted")
