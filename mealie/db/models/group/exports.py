from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class GroupDataExportsModel(TortoiseModel):
    __tablename__ = "group_data_exports"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="data_exports",
        source_field="group_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = fields.TextField(null=False)
    filename = fields.TextField(null=False)
    path = fields.TextField(null=False)
    size = fields.TextField(null=False)
    expires = fields.TextField(null=False)

    class Meta:
        table = "group_data_exports"
