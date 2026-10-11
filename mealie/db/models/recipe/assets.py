from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeAsset(RecipeBase):
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="assets",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str | None] = UnboundedCharField(null=True)
    icon: fields.TextField[str | None] = UnboundedCharField(null=True)
    file_name: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "recipe_assets"
