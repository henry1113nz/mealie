from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class Tool(TortoiseModel):
    __tablename__ = "tools"
    __filterable_fields__ = {"name", "group_id", "id", "slug"}
    __association_proxies__ = {}
    model_config = {"exclude": {"households_with_tool"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="tools",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = StringField(null=False, db_index=True)
    slug = StringField(null=False, db_index=True)
    on_hand = fields.BooleanField(null=True, default=False)
    households_with_tool = fields.ManyToManyField(
        "models.Household",
        related_name="tools_on_hand",
        through="households_to_tools",
        backward_key="tool_id",
        forward_key="household_id",
    )
    recipe_count: int = 0

    class Meta:
        table = "tools"
        unique_together = (("slug", "group_id"),)
