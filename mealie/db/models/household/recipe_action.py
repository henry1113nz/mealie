from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household


class GroupRecipeAction(TortoiseModel):
    __tablename__ = "recipe_actions"
    __filterable_fields__ = {"title", "id", "household_id", "group_id", "action_type"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="recipe_actions",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="recipe_actions",
        source_field="household_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    action_type = StringField(null=False, db_index=True)
    title = StringField(null=False, db_index=True)
    url = fields.TextField(null=False)

    class Meta:
        table = "recipe_actions"
