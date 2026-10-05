from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeAsset(TortoiseModel):
    __tablename__ = "recipe_assets"
    __filterable_fields__ = {"name", "id", "recipe_id", "icon", "file_name"}
    __association_proxies__ = {}

    id = fields.IntField(primary_key=True)
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="assets",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = fields.TextField(null=True)
    icon = fields.TextField(null=True)
    file_name = fields.TextField(null=True)

    class Meta:
        table = "recipe_assets"
