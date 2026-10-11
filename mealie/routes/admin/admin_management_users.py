from functools import cached_property

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4

from mealie.core import security
from mealie.routes._base import BaseAdminController, controller
from mealie.routes._base.mixins import AsyncHttpRepo
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.responses import ErrorResponse
from mealie.schema.user.auth import UnlockResults
from mealie.schema.user.user import UserIn, UserOut, UserPagination
from mealie.schema.user.user_passwords import ForgotPassword, PasswordResetToken
from mealie.services.user_services.password_reset_service import PasswordResetService
from mealie.services.user_services.user_service import UserService

router = APIRouter(prefix="/users")


@controller(router)
class AdminUserManagementRoutes(BaseAdminController):
    @cached_property
    def repo(self):
        return self.repos.users

    # =======================================================================
    # CRUD Operations

    @property
    def mixins(self):
        return AsyncHttpRepo[UserIn, UserOut, UserOut](self.repo, self.logger, self.registered_exceptions)

    @router.get("", response_model=UserPagination)
    async def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = await self.repo.page_all(
            pagination=q,
            override=UserOut,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=UserOut, status_code=201)
    async def create_one(self, data: UserIn):
        if await self.repos.users.get_by_username(data.username):
            raise HTTPException(status.HTTP_409_CONFLICT, {"message": self.t("exceptions.username-conflict-error")})
        elif await self.repos.users.get_one(data.email, "email"):
            raise HTTPException(status.HTTP_409_CONFLICT, {"message": self.t("exceptions.email-conflict-error")})

        data.password = security.hash_password(data.password)
        return await self.mixins.create_one(data)

    @router.post("/unlock", response_model=UnlockResults)
    async def unlock_users(self, force: bool = False) -> UnlockResults:
        user_service = UserService(self.repos)
        unlocked = await user_service.reset_locked_users(force=force)

        return UnlockResults(unlocked=unlocked)

    @router.get("/{item_id}", response_model=UserOut)
    async def get_one(self, item_id: UUID4):
        return await self.mixins.get_one(item_id)

    @router.put("/{item_id}", response_model=UserOut)
    async def update_one(self, item_id: UUID4, data: UserOut):
        # Prevent self demotion
        if self.user.id == item_id and self.user.admin != data.admin:
            raise HTTPException(status_code=403, detail=ErrorResponse.respond("you cannot demote yourself"))

        return await self.mixins.update_one(data, item_id)

    @router.delete("/{item_id}", response_model=UserOut)
    async def delete_one(self, item_id: UUID4):
        return await self.mixins.delete_one(item_id)

    @router.post("/password-reset-token", response_model=PasswordResetToken, status_code=201)
    async def generate_token(self, email: ForgotPassword):
        """Generates a reset token and returns it. This is an authenticated endpoint"""
        f_service = PasswordResetService(self.session)
        token_entry = await f_service.generate_reset_token(email.email)
        if not token_entry:
            raise HTTPException(status_code=500, detail=ErrorResponse.respond("error while generating reset token"))
        return PasswordResetToken(token=token_entry.token)
