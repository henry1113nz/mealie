from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UTCDateTimeField, UUIDField

from ._base import RecipeBase, utc_now

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class RecipeTimelineEvent(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="timeline_events",
        source_field="recipe_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="recipe_timeline_events",
        source_field="user_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    subject: fields.TextField[str] = UnboundedCharField()
    message: fields.TextField[str | None] = UnboundedCharField(null=True)
    event_type: fields.TextField[str | None] = UnboundedCharField(null=True)
    image: fields.TextField[str | None] = UnboundedCharField(null=True)
    timestamp: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True, db_index=True, default=utc_now)

    class Meta:
        table = "recipe_timeline_events"
