from datetime import UTC, datetime
from functools import cached_property

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import UUID4

from mealie.db.models.tortoise_models import GroupWebhooksModel
from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.household.webhook import CreateWebhook, ReadWebhook, WebhookPagination
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.scheduler.tasks.post_webhooks import post_group_webhooks, post_test_webhook

router = APIRouter(prefix="/households/webhooks", tags=["Households: Webhooks"])


@controller(router)
class ReadWebhookController(BaseUserController):
    @cached_property
    def repo(self):
        return self.repos.webhooks

    async def _get_webhook(self, item_id: UUID4) -> GroupWebhooksModel:
        webhook = await GroupWebhooksModel.filter(id=item_id, household_id=self.household_id).first()
        if webhook is None:
            raise HTTPException(status_code=404, detail="Not found.")
        return webhook

    @router.get("", response_model=WebhookPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repo.page_all(
            pagination=q,
            override=ReadWebhook,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=ReadWebhook, status_code=201)
    async def create_one(self, data: CreateWebhook):
        webhook = await GroupWebhooksModel.create(
            **data.model_dump(), group_id=self.group_id, household_id=self.household_id
        )
        return ReadWebhook.model_validate(webhook)

    @router.post("/rerun")
    async def rerun_webhooks(self):
        """Manually re-fires all previously scheduled webhooks for today"""

        start_time = datetime.min.time()
        start_dt = datetime.combine(datetime.now(UTC).date(), start_time)
        await post_group_webhooks(start_dt=start_dt, group_id=self.group.id, household_id=self.household.id)

    @router.get("/{item_id}", response_model=ReadWebhook)
    async def get_one(self, item_id: UUID4):
        return ReadWebhook.model_validate(await self._get_webhook(item_id))

    @router.post("/{item_id}/test")
    async def test_one(self, item_id: UUID4, bg_tasks: BackgroundTasks):
        webhook = ReadWebhook.model_validate(await self._get_webhook(item_id))
        bg_tasks.add_task(post_test_webhook, webhook, "Test Webhook")

    @router.put("/{item_id}", response_model=ReadWebhook)
    async def update_one(self, item_id: UUID4, data: CreateWebhook):
        webhook = await self._get_webhook(item_id)
        await GroupWebhooksModel.filter(id=webhook.id).update(**data.model_dump())
        return ReadWebhook.model_validate(await self._get_webhook(item_id))

    @router.delete("/{item_id}", response_model=ReadWebhook)
    async def delete_one(self, item_id: UUID4):
        webhook = await self._get_webhook(item_id)
        result = ReadWebhook.model_validate(webhook)
        await webhook.delete()
        return result
