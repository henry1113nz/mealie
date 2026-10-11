from datetime import UTC, datetime, time
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import NaiveTimeField, TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from .household import Household


class GroupWebhooksModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="webhooks",
        source_field="group_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="webhooks",
        source_field="household_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    enabled: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    name: fields.TextField[str | None] = UnboundedCharField(null=True)
    url: fields.TextField[str | None] = UnboundedCharField(null=True)
    webhook_type: fields.TextField[str | None] = UnboundedCharField(null=True, default="")
    scheduled_time: fields.TimeField[time | None] = NaiveTimeField(null=True, default=lambda: datetime.now(UTC).time())
    time: fields.TextField[str | None] = UnboundedCharField(null=True, default="00:00")

    class Meta:
        table = "webhook_urls"
