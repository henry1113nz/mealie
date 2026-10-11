"""Temporary relationship/filter projections for the unconverted recipe domain.

Application household persistence uses models.household and Tortoise. These
mappings remain for legacy recipe relationships, query metadata and bootstrap;
they must not be used for household application CRUD.
"""

from .cookbook import CookBook
from .events import GroupEventNotifierModel, GroupEventNotifierOptionsModel
from .household import Household
from .household_to_recipe import HouseholdToRecipe
from .invite_tokens import GroupInviteToken
from .mealplan import GroupMealPlan, GroupMealPlanRules
from .preferences import HouseholdPreferencesModel
from .recipe_action import GroupRecipeAction
from .shopping_list import (
    ShoppingList,
    ShoppingListExtras,
    ShoppingListItem,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
)
from .webhooks import GroupWebhooksModel

__all__ = [
    "CookBook",
    "GroupEventNotifierModel",
    "GroupEventNotifierOptionsModel",
    "GroupInviteToken",
    "GroupMealPlan",
    "GroupMealPlanRules",
    "Household",
    "HouseholdPreferencesModel",
    "HouseholdToRecipe",
    "GroupRecipeAction",
    "ShoppingList",
    "ShoppingListExtras",
    "ShoppingListItem",
    "ShoppingListItemRecipeReference",
    "ShoppingListMultiPurposeLabel",
    "ShoppingListRecipeReference",
    "GroupWebhooksModel",
]
