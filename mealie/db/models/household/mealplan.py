from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.datetime import DateField
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class GroupMealPlanRules(TortoiseModel):
    __tablename__ = "group_meal_plan_rules"
    __filterable_fields__ = {"day", "entry_type", "id", "household_id", "group_id"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="group_meal_plan_rules_group",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="group_meal_plan_rules_household",
        source_field="household_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    day = fields.TextField(null=False, default="unset")
    entry_type = fields.TextField(null=False, default="")
    query_filter_string = fields.TextField(null=False, default="")
    categories = fields.ManyToManyField(
        "models.Category",
        related_name="group_meal_plan_rules_categories",
        through="plan_rules_to_categories",
        backward_key="group_plan_rule_id",
        forward_key="category_id",
    )
    tags = fields.ManyToManyField(
        "models.Tag",
        related_name="group_meal_plan_rules_tags",
        through="plan_rules_to_tags",
        backward_key="plan_rule_id",
        forward_key="tag_id",
    )
    households = fields.ManyToManyField(
        "models.Household",
        related_name="group_meal_plan_rules_households",
        through="plan_rules_to_households",
        backward_key="group_plan_rule_id",
        forward_key="household_id",
    )

    class Meta:
        table = "group_meal_plan_rules"


class GroupMealPlan(TortoiseModel):
    __tablename__ = "group_meal_plans"
    __filterable_fields__ = {"date", "entry_type", "title", "user_id", "text", "group_id", "recipe_id"}
    __association_proxies__ = {"household_id": ["user", "household_id"], "household": ["user", "household"]}

    date = DateField(null=False, db_index=True)
    entry_type = StringField(null=False, db_index=True)
    title = StringField(null=False, db_index=True)
    text = fields.TextField(null=False)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="mealplans",
        source_field="group_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    user_id: UUID | None
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="mealplans",
        source_field="user_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="meal_entries",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
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
        table = "group_meal_plans"
        ordering = ("date", "id")
