from fastapi import APIRouter
from pydantic import UUID4

from mealie.repos.repository_factory import AllRepositories
from mealie.routes._base import BaseAdminController, controller
from mealie.routes._base.mixins import AsyncHttpRepo
from mealie.schema.group.ai_providers import (
    AIProviderCreate,
    AIProviderOut,
    AIProviderUpdate,
)

router = APIRouter(prefix="/groups/{group_id}/ai-providers")


@controller(router)
class AdminGroupAIProviderController(BaseAdminController):
    def _group_repos(self, group_id: UUID4) -> AllRepositories:
        """Return repos scoped to the target group."""
        return AllRepositories(self.session, group_id=group_id, household_id=None)

    def _mixins(self, group_id: UUID4) -> AsyncHttpRepo:
        return AsyncHttpRepo[AIProviderCreate, AIProviderOut, AIProviderUpdate](
            self._group_repos(group_id).group_ai_providers, self.logger
        )

    # =======================================================================
    # Provider CRUD

    @router.post("/providers", response_model=AIProviderOut, tags=["Admin: AI Providers"])
    async def create_ai_provider(self, group_id: UUID4, data: AIProviderCreate):
        return await self._mixins(group_id).create_one(data)

    @router.get("/providers/{provider_id}", response_model=AIProviderOut, tags=["Admin: AI Providers"])
    async def get_ai_provider(self, group_id: UUID4, provider_id: UUID4):
        return await self._mixins(group_id).get_one(provider_id)

    @router.put("/providers/{provider_id}", response_model=AIProviderOut, tags=["Admin: AI Providers"])
    async def update_ai_provider(self, group_id: UUID4, provider_id: UUID4, data: AIProviderUpdate):
        return await self._mixins(group_id).update_one(data, provider_id)

    @router.delete("/providers/{provider_id}", response_model=AIProviderOut, tags=["Admin: AI Providers"])
    async def delete_ai_provider(self, group_id: UUID4, provider_id: UUID4):
        return await self._mixins(group_id).delete_one(provider_id)
