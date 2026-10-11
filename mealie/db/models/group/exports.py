from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from .group import Group


class GroupDataExportsModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="data_exports",
        source_field="group_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    name = UnboundedCharField()
    filename = UnboundedCharField()
    path = UnboundedCharField()
    size = UnboundedCharField()
    expires = UnboundedCharField()

    class Meta:
        table = "group_data_exports"
