from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household


class GroupInviteToken(TortoiseModel):
    __tablename__ = "invite_tokens"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    token = StringField(null=False, db_index=True, unique=True)
    uses_left = fields.IntField(null=False, default=1)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="invite_tokens",
        source_field="group_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="invite_tokens",
        source_field="household_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    class Meta:
        table = "invite_tokens"
