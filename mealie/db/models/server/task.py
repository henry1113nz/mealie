from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class ServerTaskModel(TortoiseModel):
    __tablename__ = "server_tasks"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    name = fields.TextField(null=False)
    completed_date = fields.DatetimeField(null=True)
    status = fields.TextField(null=False)
    log = fields.TextField(null=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="server_tasks",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    class Meta:
        table = "server_tasks"
