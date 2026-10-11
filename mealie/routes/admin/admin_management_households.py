from functools import cached_property

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4

from mealie.db.models.users.users import User
from mealie.schema.household.household import (
    HouseholdCreate,
    HouseholdInDB,
    HouseholdPagination,
    UpdateHouseholdAdmin,
)
from mealie.schema.mapper import mapper
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.responses import ErrorResponse
from mealie.services.household_services.household_service import HouseholdService

from .._base import BaseAdminController, controller
from .._base.mixins import AsyncHttpRepo

router = APIRouter(prefix="/households")


@controller(router)
class AdminHouseholdManagementRoutes(BaseAdminController):
    @cached_property
    def repo(self):
        if not self.user:
            raise Exception("No user is logged in.")

        return self.repos.households

    # =======================================================================
    # CRUD Operations

    @property
    def mixins(self):
        return AsyncHttpRepo[HouseholdCreate, HouseholdInDB, UpdateHouseholdAdmin](
            self.repo,
            self.logger,
            self.registered_exceptions,
        )

    @router.get("", response_model=HouseholdPagination)
    async def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = await self.repo.page_all(
            pagination=q,
            override=HouseholdInDB,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=HouseholdInDB, status_code=status.HTTP_201_CREATED)
    async def create_one(self, data: HouseholdCreate):
        return await HouseholdService.create_household(self.repos, data)

    @router.get("/{item_id}", response_model=HouseholdInDB)
    async def get_one(self, item_id: UUID4):
        return await self.mixins.get_one(item_id)

    @router.put("/{item_id}", response_model=HouseholdInDB)
    async def update_one(self, item_id: UUID4, data: UpdateHouseholdAdmin):
        household = await self.repo.get_one(item_id)

        if data.preferences:
            preferences = await self.repos.household_preferences.get_one(value=item_id, key="household_id")
            preferences = mapper(data.preferences, preferences)
            household.preferences = await self.repos.household_preferences.update(item_id, preferences)

        if data.name not in ["", household.name]:
            # only update the household if the name changed, since the name is the only field that can be updated
            household.name = data.name
            household = await self.repo.update(item_id, household)

        return household

    @router.delete("/{item_id}", response_model=HouseholdInDB)
    async def delete_one(self, item_id: UUID4):
        item = await self.repo.get_one(item_id)
        if item:
            user_count = await User.filter(group_id=item.group_id, household_id=item_id).count()
            if user_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorResponse.respond(message="Cannot delete household with users"),
                )

        return await self.mixins.delete_one(item_id)
