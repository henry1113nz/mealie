from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.datetime import TimeField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household


class GroupWebhooksModel(TortoiseModel):
    __tablename__ = "webhook_urls"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="webhooks",
        source_field="group_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="webhooks",
        source_field="household_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    enabled = fields.BooleanField(null=True, default=False)
    name = fields.TextField(null=True)
    url = fields.TextField(null=True)
    webhook_type = fields.TextField(null=True, default="")
    scheduled_time = TimeField(null=True, default=lambda: datetime.now(UTC).time())
    time = fields.TextField(null=True, default="00:00")

    class Meta:
        table = "webhook_urls"
