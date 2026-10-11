from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from ..recipe.ingredient import IngredientFoodModel
    from ..recipe.tool import Tool
    from ..users.users import User
    from .mealplan import GroupMealPlanRules
    from .preferences import HouseholdPreferencesModel


class Household(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    name = UnboundedCharField(db_index=True)
    slug: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="households",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    users: fields.ReverseRelation[User]
    preferences: fields.ReverseRelation[HouseholdPreferencesModel]
    matching_meal_plan_rules: fields.ManyToManyRelation[GroupMealPlanRules]

    ingredient_foods_on_hand: fields.ManyToManyRelation[IngredientFoodModel]
    tools_on_hand: fields.ManyToManyRelation[Tool]

    class Meta:
        table = "households"
        unique_together = (("group", "name"), ("group", "slug"))

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._household_coexistence import delete_household_dependents

        if using_db is not None:
            await delete_household_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_household_dependents(self.id, connection)
                await super().delete(using_db=connection)
