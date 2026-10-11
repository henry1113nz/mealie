from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UTCDateTimeField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeShareTokenModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="recipe_share_tokens",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="share_tokens",
        source_field="recipe_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    expires_at: fields.DatetimeField[datetime] = UTCDateTimeField()

    class Meta:
        table = "recipe_share_tokens"
