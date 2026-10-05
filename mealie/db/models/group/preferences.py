from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class GroupPreferencesModel(TortoiseModel):
    __tablename__ = "group_preferences"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.OneToOneRelation[Group] = fields.OneToOneField(
        "models.Group",
        related_name="preferences",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    private_group = fields.BooleanField(null=True, default=True)
    show_announcements = fields.BooleanField(null=False, default=True)
    first_day_of_week = fields.IntField(null=True, default=0)
    recipe_public = fields.BooleanField(null=True, default=True)
    recipe_show_nutrition = fields.BooleanField(null=True, default=False)
    recipe_show_assets = fields.BooleanField(null=True, default=False)
    recipe_landscape_view = fields.BooleanField(null=True, default=False)
    recipe_disable_comments = fields.BooleanField(null=True, default=False)
    recipe_disable_amount = fields.BooleanField(null=True, default=True)

    class Meta:
        table = "group_preferences"
