from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class Nutrition(RecipeBase):
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="nutrition",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    calories: fields.TextField[str | None] = UnboundedCharField(null=True)
    carbohydrate_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    cholesterol_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    fat_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    fiber_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    protein_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    saturated_fat_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    sodium_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    sugar_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    trans_fat_content: fields.TextField[str | None] = UnboundedCharField(null=True)
    unsaturated_fat_content: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "recipe_nutrition"
