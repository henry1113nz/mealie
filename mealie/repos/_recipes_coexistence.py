"""Native recipe cascades against the existing schema, in one async transaction.

The existing foreign keys deliberately remain restrictive. Explicit ownership
edges remove children; nullable references retain the referring parent objects.
"""

from datetime import UTC, datetime

from tortoise import Model
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.expressions import Q

from mealie.db.models.household import (
    GroupMealPlan,
    HouseholdToRecipe,
    ShoppingListItem,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
)
from mealie.db.models.recipe import (
    ApiExtras,
    Category,
    IngredientFoodAliasModel,
    IngredientFoodExtras,
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    IngredientUnitAliasModel,
    IngredientUnitModel,
    MultiPurposeLabel,
    Note,
    Nutrition,
    RecipeAsset,
    RecipeComment,
    RecipeIngredientModel,
    RecipeIngredientRefLink,
    RecipeIngredientSubstitutionModel,
    RecipeInstruction,
    RecipeModel,
    RecipeNoteRefLink,
    RecipeSettings,
    RecipeShareTokenModel,
    RecipeTimelineEvent,
    Tag,
    Tool,
)
from mealie.db.models.users.user_to_recipe import UserToRecipe
from mealie.db.models.users.users import User


async def delete_recipe_dependents(entry: Model, using_db: BaseDBAsyncClient) -> None:
    now = datetime.now(UTC)
    if isinstance(entry, RecipeModel):
        await entry.recipe_category.clear(using_db=using_db)
        await entry.tags.clear(using_db=using_db)
        await entry.tools.clear(using_db=using_db)
        await (
            RecipeIngredientModel.filter(referenced_recipe_id=entry.id)
            .using_db(using_db)
            .update(referenced_recipe_id=None, update_at=now)
        )
        await User.filter(owned_recipes_id=entry.id).using_db(using_db).update(owned_recipes_id=None, update_at=now)
        ingredient_ids = (
            await RecipeIngredientModel.filter(recipe_id=entry.id).using_db(using_db).values_list("id", flat=True)
        )
        await RecipeIngredientSubstitutionModel.filter(ingredient_id__in=ingredient_ids).using_db(using_db).delete()
        instructions = (
            await RecipeInstruction.filter(recipe_id=entry.id).using_db(using_db).values_list("id", flat=True)
        )
        await RecipeIngredientRefLink.filter(instruction_id__in=instructions).using_db(using_db).delete()
        await RecipeNoteRefLink.filter(instruction_id__in=instructions).using_db(using_db).delete()
        children: tuple[type[Model], ...] = (
            RecipeIngredientModel,
            RecipeInstruction,
            RecipeComment,
            RecipeTimelineEvent,
            RecipeShareTokenModel,
            RecipeAsset,
            RecipeSettings,
            Nutrition,
            Note,
            UserToRecipe,
            HouseholdToRecipe,
            GroupMealPlan,
            ShoppingListRecipeReference,
            ShoppingListItemRecipeReference,
        )
        for model in children:
            await model.filter(recipe_id=entry.id).using_db(using_db).delete()
        await ApiExtras.filter(recipee_id=entry.id).using_db(using_db).delete()
    elif isinstance(entry, RecipeIngredientModel):
        await RecipeIngredientSubstitutionModel.filter(ingredient_id=entry.id).using_db(using_db).delete()
    elif isinstance(entry, RecipeInstruction):
        await RecipeIngredientRefLink.filter(instruction_id=entry.id).using_db(using_db).delete()
        await RecipeNoteRefLink.filter(instruction_id=entry.id).using_db(using_db).delete()
    elif isinstance(entry, IngredientFoodModel):
        await entry.households_with_ingredient_food.clear(using_db=using_db)
        await RecipeIngredientModel.filter(food_id=entry.id).using_db(using_db).update(food_id=None, update_at=now)
        await ShoppingListItem.filter(food_id=entry.id).using_db(using_db).update(food_id=None, update_at=now)
        await IngredientFoodAliasModel.filter(food_id=entry.id).using_db(using_db).delete()
        await IngredientFoodExtras.filter(ingredient_food_id=entry.id).using_db(using_db).delete()
        await (
            IngredientFoodSubstitutionModel.filter(Q(food_id=entry.id) | Q(substitute_food_id=entry.id))
            .using_db(using_db)
            .delete()
        )
        await RecipeIngredientSubstitutionModel.filter(substitute_food_id=entry.id).using_db(using_db).delete()
    elif isinstance(entry, IngredientUnitModel):
        await RecipeIngredientModel.filter(unit_id=entry.id).using_db(using_db).update(unit_id=None, update_at=now)
        await ShoppingListItem.filter(unit_id=entry.id).using_db(using_db).update(unit_id=None, update_at=now)
        await IngredientUnitAliasModel.filter(unit_id=entry.id).using_db(using_db).delete()
    elif isinstance(entry, MultiPurposeLabel):
        await IngredientFoodModel.filter(label_id=entry.id).using_db(using_db).update(label_id=None, update_at=now)
        await ShoppingListItem.filter(label_id=entry.id).using_db(using_db).update(label_id=None, update_at=now)
        await ShoppingListMultiPurposeLabel.filter(label_id=entry.id).using_db(using_db).delete()
    elif isinstance(entry, (Category, Tag, Tool)):
        await entry.recipes.clear(using_db=using_db)
        await entry.cookbooks.clear(using_db=using_db)
        if isinstance(entry, (Category, Tag)):
            await entry.meal_plan_rules.clear(using_db=using_db)
        if isinstance(entry, Category):
            await entry.groups.clear(using_db=using_db)
        if isinstance(entry, Tool):
            await entry.households_with_tool.clear(using_db=using_db)
