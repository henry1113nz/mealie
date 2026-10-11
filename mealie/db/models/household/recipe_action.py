from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from .household import Household


class GroupRecipeAction(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="recipe_actions",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="recipe_actions",
        source_field="household_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    action_type = UnboundedCharField(db_index=True)
    title = UnboundedCharField(db_index=True)
    url = UnboundedCharField()

    class Meta:
        table = "recipe_actions"
