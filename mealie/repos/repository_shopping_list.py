from mealie.db.models.household.shopping_list import ShoppingList
from mealie.schema.household.group_shopping_list import ShoppingListOut

from .repository_household_base import AsyncHouseholdRepository


class RepositoryShoppingList(AsyncHouseholdRepository[ShoppingListOut, ShoppingList]):
    pass
