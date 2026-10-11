from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.cookbook import CookBook
    from mealie.db.models.household.mealplan import GroupMealPlanRules
    from mealie.db.models.recipe.recipe import RecipeModel


class Category(RecipeBase):
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="owned_categories",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    name: fields.TextField[str] = UnboundedCharField(db_index=True)
    slug: fields.TextField[str] = UnboundedCharField(db_index=True)
    recipes: fields.ManyToManyRelation[RecipeModel]
    groups: fields.ManyToManyRelation[Group] = fields.ManyToManyField(
        "models.Group",
        related_name="categories",
        through="group_to_categories",
        backward_key="category_id",
        forward_key="group_id",
        on_delete=fields.RESTRICT,
    )

    cookbooks: fields.ManyToManyRelation[CookBook]
    meal_plan_rules: fields.ManyToManyRelation[GroupMealPlanRules]

    class Meta:
        table = "categories"
        unique_together = (("slug", "group"),)
