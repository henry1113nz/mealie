from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import CalendarDateField, TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from ..recipe.category import Category
    from ..recipe.recipe import RecipeModel
    from ..recipe.tag import Tag
    from ..users.users import User
    from .household import Household


class GroupMealPlanRules(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="meal_plan_rules",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="meal_plan_rules",
        source_field="household_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    day = UnboundedCharField(default="unset")
    entry_type = UnboundedCharField(default="")
    query_filter_string = UnboundedCharField(default="")
    households: fields.ManyToManyRelation[Household] = fields.ManyToManyField(
        "models.Household",
        related_name="matching_meal_plan_rules",
        through="plan_rules_to_households",
        backward_key="group_plan_rule_id",
        forward_key="household_id",
        on_delete=fields.RESTRICT,
    )

    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models.Category",
        related_name="meal_plan_rules",
        through="plan_rules_to_categories",
        backward_key="group_plan_rule_id",
        forward_key="category_id",
        on_delete=fields.RESTRICT,
    )
    tags: fields.ManyToManyRelation[Tag] = fields.ManyToManyField(
        "models.Tag",
        related_name="meal_plan_rules",
        through="plan_rules_to_tags",
        backward_key="plan_rule_id",
        forward_key="tag_id",
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "group_meal_plan_rules"

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._household_coexistence import delete_meal_plan_rule_dependents

        if using_db is not None:
            await delete_meal_plan_rule_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_meal_plan_rule_dependents(self.id, connection)
                await super().delete(using_db=connection)


class GroupMealPlan(TortoiseBase):
    date: fields.DateField[date] = CalendarDateField(db_index=True)
    entry_type = UnboundedCharField(db_index=True)
    title = UnboundedCharField(db_index=True)
    text = UnboundedCharField()
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="mealplans",
        source_field="group_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    user_id: UUID | None
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="mealplans",
        source_field="user_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="meal_entries",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "group_meal_plans"
