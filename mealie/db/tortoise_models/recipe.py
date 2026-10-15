from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

from ._base import TortoiseBaseModel

if TYPE_CHECKING:
    from .group import Group
    from .user import User


class Recipe(TortoiseBaseModel):
    """Recipe core columns, without runtime construction or route behavior."""

    slug = fields.CharField(max_length=255, null=True, db_index=True)
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group", related_name="recipes", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="recipes", null=True, on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    rating = fields.FloatField(null=True, db_index=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    image = fields.CharField(max_length=255, null=True)
    total_time = fields.CharField(max_length=255, null=True)
    prep_time = fields.CharField(max_length=255, null=True)
    perform_time = fields.CharField(max_length=255, null=True)
    total_time_seconds = fields.IntField(null=True)
    prep_time_seconds = fields.IntField(null=True)
    perform_time_seconds = fields.IntField(null=True)
    recipe_yield = fields.CharField(max_length=255, null=True)
    recipe_yield_quantity = fields.FloatField(default=0, db_index=True)
    recipe_servings = fields.FloatField(default=0, db_index=True)
    org_url = fields.CharField(max_length=255, null=True)
    date_added = fields.DateField(default=date.today, null=True)
    date_updated = fields.DatetimeField(null=True)
    last_made = fields.DatetimeField(null=True)
    name_normalized = fields.CharField(max_length=255, db_index=True)
    description_normalized = fields.CharField(max_length=2048, null=True, db_index=True)
    cook_time = fields.CharField(max_length=255, null=True)
    recipeCuisine = fields.CharField(max_length=255, null=True)
    is_ocr_recipe = fields.BooleanField(default=False, null=True)
    recipe_category = fields.ManyToManyField(
        "models.Category",
        through="recipes_to_categories",
        forward_key="category_id",
        backward_key="recipe_id",
        related_name="recipes",
    )
    tags = fields.ManyToManyField(
        "models.Tag",
        through="recipes_to_tags",
        forward_key="tag_id",
        backward_key="recipe_id",
        related_name="recipes",
    )
    tools = fields.ManyToManyField(
        "models.Tool",
        through="recipes_to_tools",
        forward_key="tool_id",
        backward_key="recipe_id",
        related_name="recipes",
    )

    class Meta:
        table = "recipes"
        unique_together = (("slug", "group"),)


class RecipeNutrition(Model):
    id = fields.IntField(primary_key=True)
    recipe: fields.ForeignKeyNullableRelation[Recipe] = fields.ForeignKeyField(
        "models.Recipe", related_name="nutrition_rows", null=True, on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    calories = fields.CharField(max_length=255, null=True)
    carbohydrate_content = fields.CharField(max_length=255, null=True)
    cholesterol_content = fields.CharField(max_length=255, null=True)
    fat_content = fields.CharField(max_length=255, null=True)
    fiber_content = fields.CharField(max_length=255, null=True)
    protein_content = fields.CharField(max_length=255, null=True)
    saturated_fat_content = fields.CharField(max_length=255, null=True)
    sodium_content = fields.CharField(max_length=255, null=True)
    sugar_content = fields.CharField(max_length=255, null=True)
    trans_fat_content = fields.CharField(max_length=255, null=True)
    unsaturated_fat_content = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_nutrition"
