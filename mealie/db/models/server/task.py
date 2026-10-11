from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UTCDateTimeField

if TYPE_CHECKING:
    from ..group.group import Group


class ServerTaskModel(TortoiseBase):
    """Deprecated server tasks retained for database and backup compatibility."""

    name = fields.TextField()
    completed_date: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True)
    status = fields.TextField()
    log: fields.TextField[str | None] = fields.TextField(null=True)

    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group", related_name="server_tasks", source_field="group_id", db_index=True, on_delete=fields.RESTRICT
    )

    class Meta:
        table = "server_tasks"
