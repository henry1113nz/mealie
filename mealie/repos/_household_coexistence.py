"""Native household cascades sharing the caller's Tortoise transaction."""

from datetime import UTC, datetime
from uuid import UUID

from tortoise.backends.base.client import BaseDBAsyncClient

from mealie.db.models.household import (
    CookBook,
    GroupEventNotifierModel,
    GroupEventNotifierOptionsModel,
    GroupInviteToken,
    GroupMealPlan,
    GroupMealPlanRules,
    GroupRecipeAction,
    GroupWebhooksModel,
    Household,
    HouseholdPreferencesModel,
    HouseholdToRecipe,
    ShoppingList,
    ShoppingListExtras,
    ShoppingListItem,
    ShoppingListItemExtras,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
)
from mealie.db.models.users.users import User


async def delete_shopping_list_item_dependents(item_id: UUID, using_db: BaseDBAsyncClient) -> None:
    await ShoppingListItemRecipeReference.filter(shopping_list_item_id=item_id).using_db(using_db).delete()
    await ShoppingListItemExtras.filter(shopping_list_item_id=item_id).using_db(using_db).delete()


async def delete_shopping_list_dependents(list_id: UUID, using_db: BaseDBAsyncClient) -> None:
    item_ids = await ShoppingListItem.filter(shopping_list_id=list_id).using_db(using_db).values_list("id", flat=True)
    await ShoppingListItemRecipeReference.filter(shopping_list_item_id__in=item_ids).using_db(using_db).delete()
    await ShoppingListItemExtras.filter(shopping_list_item_id__in=item_ids).using_db(using_db).delete()
    await ShoppingListItem.filter(shopping_list_id=list_id).using_db(using_db).delete()
    await ShoppingListRecipeReference.filter(shopping_list_id=list_id).using_db(using_db).delete()
    await ShoppingListMultiPurposeLabel.filter(shopping_list_id=list_id).using_db(using_db).delete()
    await ShoppingListExtras.filter(shopping_list_id=list_id).using_db(using_db).delete()


async def delete_notifier_dependents(notifier_id: UUID, using_db: BaseDBAsyncClient) -> None:
    await GroupEventNotifierOptionsModel.filter(event_notifier_id=notifier_id).using_db(using_db).delete()


async def delete_cookbook_dependents(cookbook_id: UUID, using_db: BaseDBAsyncClient) -> None:
    cookbook = await CookBook.filter(id=cookbook_id).using_db(using_db).get()
    await cookbook.categories.clear(using_db=using_db)
    await cookbook.tags.clear(using_db=using_db)
    await cookbook.tools.clear(using_db=using_db)


async def delete_meal_plan_rule_dependents(rule_id: UUID, using_db: BaseDBAsyncClient) -> None:
    rule = await GroupMealPlanRules.filter(id=rule_id).using_db(using_db).get()
    await rule.households.clear(using_db=using_db)
    await rule.categories.clear(using_db=using_db)
    await rule.tags.clear(using_db=using_db)


async def delete_household_dependents(household_id: UUID, using_db: BaseDBAsyncClient) -> None:
    # Users and their recipes/lists survive household deletion, as before.
    await (
        User.filter(household_id=household_id).using_db(using_db).update(household_id=None, update_at=datetime.now(UTC))
    )
    await (
        GroupMealPlanRules.filter(household_id=household_id)
        .using_db(using_db)
        .update(household_id=None, update_at=datetime.now(UTC))
    )
    household = await Household.filter(id=household_id).using_db(using_db).get()
    await household.matching_meal_plan_rules.clear(using_db=using_db)
    for model in (CookBook, GroupEventNotifierModel):
        for entry in await model.filter(household_id=household_id).using_db(using_db):
            await entry.delete(using_db=using_db)
    for simple_model in (
        GroupInviteToken,
        GroupRecipeAction,
        GroupWebhooksModel,
        HouseholdPreferencesModel,
        HouseholdToRecipe,
    ):
        await simple_model.filter(household_id=household_id).using_db(using_db).delete()
    await household.ingredient_foods_on_hand.clear(using_db=using_db)
    await household.tools_on_hand.clear(using_db=using_db)


async def delete_group_household_dependents(group_id: UUID, using_db: BaseDBAsyncClient) -> None:
    for model in (Household, CookBook, GroupEventNotifierModel, GroupMealPlanRules, ShoppingList):
        for entry in await model.filter(group_id=group_id).using_db(using_db):
            await entry.delete(using_db=using_db)
    for simple_model in (GroupInviteToken, GroupRecipeAction, GroupWebhooksModel, GroupMealPlan):
        await simple_model.filter(group_id=group_id).using_db(using_db).delete()
