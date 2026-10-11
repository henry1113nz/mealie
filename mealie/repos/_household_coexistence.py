"""Native household cascades and the remaining recipe association boundary.

All writes share the caller's Tortoise transaction. Only associations to recipe
models still need explicit SQL until their C6 conversion.
"""

from datetime import UTC, datetime
from typing import Any
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


async def delete_recipe_links(table: str, column: str, identifier: UUID, using_db: BaseDBAsyncClient) -> None:
    # Identifiers are internal constants; values are always bound parameters.
    postgres = using_db.capabilities.dialect == "postgres"
    await using_db.execute_query(
        f'DELETE FROM "{table}" WHERE "{column}" = {"$1" if postgres else "?"}',
        [str(identifier) if postgres else identifier.hex],
    )


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
    for table in ("cookbooks_to_categories", "cookbooks_to_tags", "cookbooks_to_tools"):
        await delete_recipe_links(table, "cookbook_id", cookbook_id, using_db)


async def delete_meal_plan_rule_dependents(rule_id: UUID, using_db: BaseDBAsyncClient) -> None:
    rule = await GroupMealPlanRules.filter(id=rule_id).using_db(using_db).get()
    await rule.households.clear(using_db=using_db)
    await delete_recipe_links("plan_rules_to_categories", "group_plan_rule_id", rule_id, using_db)
    await delete_recipe_links("plan_rules_to_tags", "plan_rule_id", rule_id, using_db)


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
    for table in ("households_to_ingredient_foods", "households_to_tools"):
        await delete_recipe_links(table, "household_id", household_id, using_db)


async def delete_group_household_dependents(group_id: UUID, using_db: BaseDBAsyncClient) -> None:
    for model in (Household, CookBook, GroupEventNotifierModel, GroupMealPlanRules, ShoppingList):
        for entry in await model.filter(group_id=group_id).using_db(using_db):
            await entry.delete(using_db=using_db)
    for simple_model in (GroupInviteToken, GroupRecipeAction, GroupWebhooksModel, GroupMealPlan):
        await simple_model.filter(group_id=group_id).using_db(using_db).delete()


async def clear_recipe_domain_references(identifiers: dict[str, list[Any]], using_db: BaseDBAsyncClient) -> None:
    """Remove links to deleted recipes, retaining other households' parent rows."""
    recipes = identifiers["recipes"]
    await HouseholdToRecipe.filter(recipe_id__in=recipes).using_db(using_db).delete()
    await GroupMealPlan.filter(recipe_id__in=recipes).using_db(using_db).delete()
    await ShoppingListRecipeReference.filter(recipe_id__in=recipes).using_db(using_db).delete()
    await ShoppingListItemRecipeReference.filter(recipe_id__in=recipes).using_db(using_db).delete()
    await (
        ShoppingListMultiPurposeLabel.filter(label_id__in=identifiers["multi_purpose_labels"])
        .using_db(using_db)
        .delete()
    )
    for field, table in (
        ("food_id", "ingredient_foods"),
        ("unit_id", "ingredient_units"),
        ("label_id", "multi_purpose_labels"),
    ):
        await (
            ShoppingListItem.filter(**{f"{field}__in": identifiers[table]})
            .using_db(using_db)
            .update(**{field: None, "update_at": datetime.now(UTC)})
        )
