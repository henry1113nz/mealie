from datetime import datetime
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UTCDateTimeField, UUIDField


class ServerTaskModel(TortoiseBase):
    """Deprecated server tasks retained for database and backup compatibility."""

    name = fields.TextField()
    completed_date: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True)
    status = fields.TextField()
    log: fields.TextField[str | None] = fields.TextField(null=True)

    # The existing database FK still references groups.id. Keep its scalar UUID
    # until Group is converted in C4, when this becomes a Tortoise relation.
    group_id: fields.UUIDField[UUID] = UUIDField(db_index=True)

    class Meta:
        table = "server_tasks"
