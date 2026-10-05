from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.datetime import get_utc_now

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class RecipeTimelineEvent(TortoiseModel):
    __tablename__ = "recipe_timeline_events"
    __filterable_fields__ = {"subject", "timestamp", "user_id", "id", "event_type", "image", "recipe_id", "message"}
    __association_proxies__ = {"group_id": ["recipe", "group_id"], "household_id": ["recipe", "household_id"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="timeline_events",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="recipe_timeline_events",
        source_field="user_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    subject = fields.TextField(null=False)
    message = fields.TextField(null=True)
    event_type = fields.TextField(null=True)
    image = fields.TextField(null=True)
    timestamp = fields.DatetimeField(null=True, db_index=True, default=get_utc_now)

    @property
    def group_id(self):
        parent = getattr(self, "recipe", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "recipe", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "recipe_timeline_events"
