from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeSettings(RecipeBase):
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="settings",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    public: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=True)
    show_nutrition: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=True)
    show_assets: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=True)
    landscape_view: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=True)
    disable_comments: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=False)
    locked: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=False)
    disable_amount: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=True)

    class Meta:
        table = "recipe_settings"
