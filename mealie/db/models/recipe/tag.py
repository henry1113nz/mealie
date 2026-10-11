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


class Tag(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="tags",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str] = UnboundedCharField(db_index=True)
    slug: fields.TextField[str] = UnboundedCharField(db_index=True)
    recipes: fields.ManyToManyRelation[RecipeModel]

    cookbooks: fields.ManyToManyRelation[CookBook]
    meal_plan_rules: fields.ManyToManyRelation[GroupMealPlanRules]

    class Meta:
        table = "tags"
        unique_together = (("slug", "group"),)
