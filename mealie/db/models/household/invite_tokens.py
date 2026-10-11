from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField

if TYPE_CHECKING:
    from ..group.group import Group
    from .household import Household


class GroupInviteToken(TortoiseBase):
    token = UnboundedCharField(db_index=True, unique=True)
    uses_left = fields.IntField(default=1)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="invite_tokens",
        source_field="group_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="invite_tokens",
        source_field="household_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "invite_tokens"
