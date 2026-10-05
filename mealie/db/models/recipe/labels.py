from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class MultiPurposeLabel(TortoiseModel):
    __tablename__ = "multi_purpose_labels"
    __filterable_fields__ = {"name", "group_id", "color", "id"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = fields.CharField(max_length=255, null=False)
    color = fields.CharField(max_length=10, null=False, default="")
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="labels",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    class Meta:
        table = "multi_purpose_labels"
        unique_together = (("name", "group_id"),)
