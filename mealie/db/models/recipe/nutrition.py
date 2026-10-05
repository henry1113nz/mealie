from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class Nutrition(TortoiseModel):
    __tablename__ = "recipe_nutrition"
    __filterable_fields__ = {
        "sugar_content",
        "cholesterol_content",
        "carbohydrate_content",
        "calories",
        "id",
        "protein_content",
        "saturated_fat_content",
        "fat_content",
        "sodium_content",
        "unsaturated_fat_content",
        "trans_fat_content",
        "recipe_id",
        "fiber_content",
    }
    __association_proxies__ = {}

    id = fields.IntField(primary_key=True)
    recipe_id: UUID
    recipe: fields.OneToOneRelation[RecipeModel] = fields.OneToOneField(
        "models.RecipeModel",
        related_name="nutrition",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    calories = fields.TextField(null=True)
    carbohydrate_content = fields.TextField(null=True)
    cholesterol_content = fields.TextField(null=True)
    fat_content = fields.TextField(null=True)
    fiber_content = fields.TextField(null=True)
    protein_content = fields.TextField(null=True)
    saturated_fat_content = fields.TextField(null=True)
    sodium_content = fields.TextField(null=True)
    sugar_content = fields.TextField(null=True)
    trans_fat_content = fields.TextField(null=True)
    unsaturated_fat_content = fields.TextField(null=True)

    class Meta:
        table = "recipe_nutrition"
