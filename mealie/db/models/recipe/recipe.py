from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.datetime import DateField, get_utc_today
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.users.users import User


class RecipeModel(TortoiseModel):
    __tablename__ = "recipes"
    __filterable_fields__ = {
        "id",
        "image",
        "date_updated",
        "group_id",
        "perform_time_seconds",
        "total_time",
        "recipe_servings",
        "user_id",
        "name_normalized",
        "description_normalized",
        "recipe_yield",
        "date_added",
        "recipe_yield_quantity",
        "prep_time_seconds",
        "org_url",
        "name",
        "prep_time",
        "perform_time",
        "last_made",
        "rating",
        "total_time_seconds",
        "description",
        "slug",
    }
    __association_proxies__ = {"household_id": ["user", "household_id"], "household": ["user", "household"]}
    model_config = {
        "get_attr": "slug",
        "exclude": {
            "assets",
            "notes",
            "nutrition",
            "recipe_ingredient",
            "recipe_instructions",
            "settings",
            "comments",
            "timeline_events",
        },
    }

    id = fields.UUIDField(primary_key=True, default=uuid4)
    slug = StringField(null=True, db_index=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="recipes",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    user_id: UUID | None
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="recipes",
        source_field="user_id",
        null=True,
        on_delete=fields.SET_NULL,
        db_index=True,
    )
    rating = fields.FloatField(null=True, db_index=True)
    name = fields.TextField(null=False)
    description = fields.TextField(null=True)
    image: str | None = fields.TextField(null=True)
    total_time = fields.TextField(null=True)
    prep_time = fields.TextField(null=True)
    perform_time = fields.TextField(null=True)
    total_time_seconds = fields.IntField(null=True)
    prep_time_seconds = fields.IntField(null=True)
    perform_time_seconds = fields.IntField(null=True)
    recipe_yield = fields.TextField(null=True)
    recipe_yield_quantity = fields.FloatField(null=False, db_index=True, default=0)
    recipe_servings = fields.FloatField(null=False, db_index=True, default=0)
    org_url = fields.TextField(null=True)
    date_added = DateField(null=True, default=get_utc_today)
    date_updated = fields.DatetimeField(null=True)
    last_made = fields.DatetimeField(null=True)
    name_normalized = fields.CharField(max_length=255, null=False, db_index=True)
    description_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    cook_time = fields.TextField(null=True)
    recipeCuisine = fields.TextField(null=True)
    is_ocr_recipe = fields.BooleanField(null=True, default=False)
    rated_by = fields.ManyToManyField(
        "models.User",
        related_name="rated_recipes",
        through="users_to_recipes",
        backward_key="recipe_id",
        forward_key="user_id",
    )
    recipe_category = fields.ManyToManyField(
        "models.Category",
        related_name="recipes",
        through="recipes_to_categories",
        backward_key="recipe_id",
        forward_key="category_id",
    )
    tools = fields.ManyToManyField(
        "models.Tool",
        related_name="recipes",
        through="recipes_to_tools",
        backward_key="recipe_id",
        forward_key="tool_id",
    )
    tags = fields.ManyToManyField(
        "models.Tag", related_name="recipes", through="recipes_to_tags", backward_key="recipe_id", forward_key="tag_id"
    )
    made_by = fields.ManyToManyField(
        "models.Household",
        related_name="made_recipes",
        through="households_to_recipes",
        backward_key="recipe_id",
        forward_key="household_id",
    )

    @property
    def household_id(self):
        parent = getattr(self, "user", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    @property
    def household(self):
        parent = getattr(self, "user", None)
        return getattr(parent, "household", None) if parent is not None else None

    class Meta:
        table = "recipes"
        unique_together = (("slug", "group_id"),)
