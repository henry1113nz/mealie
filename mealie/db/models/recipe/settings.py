from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeSettings(TortoiseModel):
    __tablename__ = "recipe_settings"
    __filterable_fields__ = {
        "show_nutrition",
        "landscape_view",
        "public",
        "disable_comments",
        "id",
        "locked",
        "show_assets",
        "recipe_id",
    }
    __association_proxies__ = {}

    id = fields.IntField(primary_key=True)
    recipe_id: UUID
    recipe: fields.OneToOneRelation[RecipeModel] = fields.OneToOneField(
        "models.RecipeModel",
        related_name="settings",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    public = fields.BooleanField(null=True, default=True)
    show_nutrition = fields.BooleanField(null=True, default=True)
    show_assets = fields.BooleanField(null=True, default=True)
    landscape_view = fields.BooleanField(null=True, default=True)
    disable_comments = fields.BooleanField(null=True, default=False)
    locked = fields.BooleanField(null=True, default=False)
    disable_amount = fields.BooleanField(null=True, default=True)

    class Meta:
        table = "recipe_settings"
