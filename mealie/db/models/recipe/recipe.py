from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import CalendarDateField, UnboundedCharField, UTCDateTimeField, UUIDField

from ._base import RecipeBase, utc_now, utc_today

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.recipe.api_extras import ApiExtras
    from mealie.db.models.recipe.assets import RecipeAsset
    from mealie.db.models.recipe.category import Category
    from mealie.db.models.recipe.comment import RecipeComment
    from mealie.db.models.recipe.ingredient import RecipeIngredientModel
    from mealie.db.models.recipe.instruction import RecipeInstruction
    from mealie.db.models.recipe.note import Note
    from mealie.db.models.recipe.nutrition import Nutrition
    from mealie.db.models.recipe.recipe_timeline import RecipeTimelineEvent
    from mealie.db.models.recipe.settings import RecipeSettings
    from mealie.db.models.recipe.shared import RecipeShareTokenModel
    from mealie.db.models.recipe.tag import Tag
    from mealie.db.models.recipe.tool import Tool
    from mealie.db.models.users.users import User


class RecipeModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    slug: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="recipes",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    user_id: UUID | None
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="recipes",
        source_field="user_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    rating: fields.FloatField[float | None] = fields.FloatField(null=True, db_index=True)
    name: fields.TextField[str] = UnboundedCharField()
    description: fields.TextField[str | None] = UnboundedCharField(null=True)
    image: fields.TextField[str | None] = UnboundedCharField(null=True)
    total_time: fields.TextField[str | None] = UnboundedCharField(null=True)
    prep_time: fields.TextField[str | None] = UnboundedCharField(null=True)
    perform_time: fields.TextField[str | None] = UnboundedCharField(null=True)
    total_time_seconds: fields.IntField[int | None] = fields.IntField(null=True)
    prep_time_seconds: fields.IntField[int | None] = fields.IntField(null=True)
    perform_time_seconds: fields.IntField[int | None] = fields.IntField(null=True)
    recipe_yield: fields.TextField[str | None] = UnboundedCharField(null=True)
    recipe_yield_quantity: fields.FloatField[float] = fields.FloatField(db_index=True, default=0)
    recipe_servings: fields.FloatField[float] = fields.FloatField(db_index=True, default=0)
    org_url: fields.TextField[str | None] = UnboundedCharField(null=True)
    date_added: fields.DateField[date | None] = CalendarDateField(null=True, default=utc_today)
    date_updated: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True, default=utc_now)
    last_made: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True)
    name_normalized: fields.TextField[str] = UnboundedCharField(db_index=True)
    description_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    cook_time: fields.TextField[str | None] = UnboundedCharField(null=True)
    recipeCuisine: fields.TextField[str | None] = UnboundedCharField(null=True)
    is_ocr_recipe: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=False)
    nutrition: fields.ReverseRelation[Nutrition]
    settings: fields.ReverseRelation[RecipeSettings]
    share_tokens: fields.ReverseRelation[RecipeShareTokenModel]
    assets: fields.ReverseRelation[RecipeAsset]
    recipe_ingredient: fields.ReverseRelation[RecipeIngredientModel]
    referenced_ingredients: fields.ReverseRelation[RecipeIngredientModel]
    comments: fields.ReverseRelation[RecipeComment]
    extras: fields.ReverseRelation[ApiExtras]
    recipe_instructions: fields.ReverseRelation[RecipeInstruction]
    notes: fields.ReverseRelation[Note]
    timeline_events: fields.ReverseRelation[RecipeTimelineEvent]
    recipe_category: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models.Category",
        related_name="recipes",
        through="recipes_to_categories",
        backward_key="recipe_id",
        forward_key="category_id",
        on_delete=fields.RESTRICT,
    )
    tags: fields.ManyToManyRelation[Tag] = fields.ManyToManyField(
        "models.Tag",
        related_name="recipes",
        through="recipes_to_tags",
        backward_key="recipe_id",
        forward_key="tag_id",
        on_delete=fields.RESTRICT,
    )
    tools: fields.ManyToManyRelation[Tool] = fields.ManyToManyField(
        "models.Tool",
        related_name="recipes",
        through="recipes_to_tools",
        backward_key="recipe_id",
        forward_key="tool_id",
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "recipes"
        unique_together = (("slug", "group"),)
