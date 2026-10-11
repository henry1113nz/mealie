"""Preserve reference cleanup without deleting the referring tenant's objects."""

from contextlib import nullcontext
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, insert
from tortoise.transactions import in_transaction

from mealie.db.models._legacy_household.cookbook import CookBook
from mealie.db.models._legacy_household.household_to_recipe import HouseholdToRecipe
from mealie.db.models._legacy_household.mealplan import GroupMealPlan
from mealie.db.models._legacy_household.shopping_list import (
    ShoppingList,
    ShoppingListItem,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
)
from mealie.db.models.group import Group
from mealie.db.models.recipe.category import Category, cookbooks_to_categories, recipes_to_categories
from mealie.db.models.recipe.ingredient import (
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    IngredientUnitModel,
    RecipeIngredientModel,
    RecipeIngredientSubstitutionModel,
    households_to_ingredient_foods,
)
from mealie.db.models.recipe.labels import MultiPurposeLabel
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.tag import Tag, cookbooks_to_tags, recipes_to_tags
from mealie.db.models.recipe.tool import Tool, cookbooks_to_tools, households_to_tools, recipes_to_tools
from mealie.db.models.users.users import User
from mealie.repos import _users_coexistence as bridge
from mealie.repos.all_repositories import AllRepositories
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_engine as server_engine
from tests.unit_tests.test_tortoise_server import server_settings as server_settings
from tests.unit_tests.test_tortoise_users import create_native_user
from tests.unit_tests.test_tortoise_users import native_user_repositories as native_user_repositories


@pytest.mark.asyncio
@pytest.mark.parametrize("rollback", [False, True])
async def test_group_delete_removes_recipe_links_but_preserves_other_tenant_parents(
    native_user_repositories: tuple[AllRepositories, AllRepositories], server_engine: Engine, rollback: bool
) -> None:
    repos, other = native_user_repositories
    user = await create_native_user(other, "recipe-link-survivor")
    recipe_id, kept_recipe_id, list_id, item_id = (uuid4() for _ in range(4))
    removed_refs, kept_refs = {}, {}
    with server_engine.begin() as connection:
        for group_id, identifier in ((repos.group_id, recipe_id), (other.group_id, kept_recipe_id)):
            connection.execute(
                insert(RecipeModel).values(id=identifier, group_id=group_id, name="Recipe", name_normalized="recipe")
            )
        connection.execute(insert(ShoppingList).values(id=list_id, group_id=other.group_id, user_id=user.id))
        connection.execute(insert(ShoppingListItem).values(id=item_id, shopping_list_id=list_id))
        for linked_recipe, refs in ((recipe_id, removed_refs), (kept_recipe_id, kept_refs)):
            for model, values in (
                (ShoppingListRecipeReference, {"shopping_list_id": list_id, "recipe_quantity": 1}),
                (ShoppingListItemRecipeReference, {"shopping_list_item_id": item_id, "recipe_quantity": 1}),
                (HouseholdToRecipe, {"household_id": user.household_id}),
            ):
                identifier = uuid4()
                connection.execute(insert(model).values(id=identifier, recipe_id=linked_recipe, **values))
                refs[model.__tablename__] = identifier
            result = connection.execute(
                insert(GroupMealPlan).values(
                    # NULL group_id is valid legacy data; recipe ownership still
                    # makes this meal entry dependent on the deleted recipe.
                    group_id=None,
                    user_id=user.id,
                    recipe_id=linked_recipe,
                    date=date(2026, 4, 5),
                    entry_type="dinner",
                    title="Dinner",
                    text="Dinner",
                )
            )
            refs["group_meal_plans"] = result.inserted_primary_key[0]

    with pytest.raises(RuntimeError, match="rollback reference cleanup") if rollback else nullcontext():
        async with in_transaction("default"):
            await repos.groups.delete(repos.group_id)
            for table, identifier in removed_refs.items():
                assert await bridge.related_record(table, "id", identifier) is None
            for table, identifier in kept_refs.items():
                assert await bridge.related_record(table, "id", identifier) is not None
            assert await bridge.related_record("recipes", "id", recipe_id) is None
            for table, identifier in (
                ("recipes", kept_recipe_id),
                ("shopping_lists", list_id),
                ("shopping_list_items", item_id),
                ("households", user.household_id),
            ):
                assert await bridge.related_record(table, "id", identifier) is not None
            assert await User.filter(id=user.id, group_id=other.group_id).exists()
            if rollback:
                raise RuntimeError("rollback reference cleanup")

    assert await Group.filter(id=repos.group_id).exists() is rollback
    assert (await bridge.related_record("recipes", "id", recipe_id) is not None) is rollback
    for table, identifier in removed_refs.items():
        assert (await bridge.related_record(table, "id", identifier) is not None) is rollback
    for table, identifier in kept_refs.items():
        assert await bridge.related_record(table, "id", identifier) is not None
    assert await Group.filter(id=other.group_id).exists()


@pytest.mark.asyncio
async def test_group_delete_clears_nullable_references_and_deletes_substitutions_only(
    native_user_repositories: tuple[AllRepositories, AllRepositories], server_engine: Engine
) -> None:
    repos, other = native_user_repositories
    user = await create_native_user(other, "nullable-link-survivor")
    target_household = (await repos.households.get_all())[0]
    recipe_id, kept_recipe_id, food_id, kept_food_id, unit_id, label_id, list_id, item_id = (uuid4() for _ in range(8))
    removed_substitutions, kept_substitutions = {}, {}
    with server_engine.begin() as connection:
        for group_id, identifier in ((repos.group_id, recipe_id), (other.group_id, kept_recipe_id)):
            connection.execute(
                insert(RecipeModel).values(id=identifier, group_id=group_id, name="Recipe", name_normalized="recipe")
            )
        connection.execute(insert(MultiPurposeLabel).values(id=label_id, group_id=repos.group_id, name="Target label"))
        connection.execute(insert(IngredientUnitModel).values(id=unit_id, group_id=repos.group_id, name="Target unit"))
        connection.execute(insert(IngredientFoodModel).values(id=food_id, group_id=repos.group_id, name="Target food"))
        connection.execute(
            insert(IngredientFoodModel).values(
                id=kept_food_id, group_id=other.group_id, name="Kept food", label_id=label_id
            )
        )
        ingredient_id = connection.execute(
            insert(RecipeIngredientModel).values(
                recipe_id=kept_recipe_id, referenced_recipe_id=recipe_id, food_id=food_id, unit_id=unit_id
            )
        ).inserted_primary_key[0]
        connection.execute(insert(ShoppingList).values(id=list_id, group_id=other.group_id, user_id=user.id))
        connection.execute(
            insert(ShoppingListItem).values(
                id=item_id, shopping_list_id=list_id, food_id=food_id, unit_id=unit_id, label_id=label_id
            )
        )
        label_setting_id = uuid4()
        connection.execute(
            insert(ShoppingListMultiPurposeLabel).values(
                id=label_setting_id, shopping_list_id=list_id, label_id=label_id
            )
        )
        for model, owner in (
            (IngredientFoodSubstitutionModel, {"food_id": kept_food_id}),
            (RecipeIngredientSubstitutionModel, {"ingredient_id": ingredient_id}),
        ):
            removed_id, kept_id = uuid4(), uuid4()
            connection.execute(insert(model).values(id=removed_id, substitute_food_id=food_id, **owner))
            connection.execute(insert(model).values(id=kept_id, note="Keep this independent note", **owner))
            removed_substitutions[model.__tablename__] = removed_id
            kept_substitutions[model.__tablename__] = kept_id
    user_record = await User.get(id=user.id)
    user_record.household_id = target_household.id
    user_record.owned_recipes_id = recipe_id
    await user_record.save(update_fields=["household_id", "owned_recipes_id", "update_at"])

    await repos.groups.delete(repos.group_id)

    retained_user = await User.get(id=user.id)
    assert retained_user.group_id == other.group_id
    assert retained_user.household_id is None
    assert retained_user.owned_recipes_id is None
    ingredient = await bridge.related_record("recipes_ingredients", "id", ingredient_id)
    assert ingredient is not None
    assert UUID(str(ingredient["recipe_id"])) == kept_recipe_id
    assert ingredient["referenced_recipe_id"] is None
    assert ingredient["food_id"] is None
    assert ingredient["unit_id"] is None
    item = await bridge.related_record("shopping_list_items", "id", item_id)
    assert item is not None
    assert UUID(str(item["shopping_list_id"])) == list_id
    assert item["food_id"] is None
    assert item["unit_id"] is None
    assert item["label_id"] is None
    assert (await bridge.related_record("ingredient_foods", "id", kept_food_id))["label_id"] is None
    assert await bridge.related_record("shopping_lists_multi_purpose_labels", "id", label_setting_id) is None
    for table, identifier in removed_substitutions.items():
        assert await bridge.related_record(table, "id", identifier) is None
    for table, identifier in kept_substitutions.items():
        assert (await bridge.related_record(table, "id", identifier))["note"] == "Keep this independent note"
    assert await bridge.related_record("recipes", "id", kept_recipe_id) is not None
    assert await bridge.related_record("shopping_lists", "id", list_id) is not None
    assert await Group.filter(id=other.group_id).exists()


@pytest.mark.asyncio
async def test_group_delete_removes_secondary_links_from_either_side_without_deleting_parents(
    native_user_repositories: tuple[AllRepositories, AllRepositories], server_engine: Engine
) -> None:
    repos, other = native_user_repositories
    household = (await other.households.get_all())[0]
    recipe_id, cookbook_id = uuid4(), uuid4()
    retained_links = []
    with server_engine.begin() as connection:
        connection.execute(
            insert(RecipeModel).values(
                id=recipe_id, group_id=other.group_id, name="Kept recipe", name_normalized="kept"
            )
        )
        connection.execute(
            insert(CookBook).values(
                id=cookbook_id, group_id=other.group_id, household_id=household.id, name="Kept cookbook", slug="kept"
            )
        )
        for model, foreign_key, tables in (
            (
                Category,
                "category_id",
                (
                    (recipes_to_categories, "recipe_id", recipe_id),
                    (cookbooks_to_categories, "cookbook_id", cookbook_id),
                ),
            ),
            (
                Tag,
                "tag_id",
                ((recipes_to_tags, "recipe_id", recipe_id), (cookbooks_to_tags, "cookbook_id", cookbook_id)),
            ),
            (
                Tool,
                "tool_id",
                (
                    (recipes_to_tools, "recipe_id", recipe_id),
                    (cookbooks_to_tools, "cookbook_id", cookbook_id),
                    (households_to_tools, "household_id", household.id),
                ),
            ),
            (IngredientFoodModel, "food_id", ((households_to_ingredient_foods, "household_id", household.id),)),
        ):
            for group_id in (repos.group_id, other.group_id):
                identifier = uuid4()
                values = {"id": identifier, "group_id": group_id, "name": "Linked object"}
                if model is not IngredientFoodModel:
                    values["slug"] = "linked-object"
                connection.execute(insert(model).values(**values))
                for table, parent_column, parent_id in tables:
                    connection.execute(insert(table).values(**{foreign_key: identifier, parent_column: parent_id}))
                    if group_id == other.group_id:
                        retained_links.append((table.name, foreign_key, identifier, parent_column, parent_id))

    await repos.groups.delete(repos.group_id)

    for table, foreign_key, identifier, parent_column, parent_id in retained_links:
        rows = await bridge.execute(f'SELECT * FROM "{table}"')
        assert len(rows) == 1
        assert UUID(str(rows[0][foreign_key])) == identifier
        assert UUID(str(rows[0][parent_column])) == parent_id
    assert await bridge.related_record("recipes", "id", recipe_id) is not None
    assert await bridge.related_record("cookbooks", "id", cookbook_id) is not None
    assert await bridge.related_record("households", "id", household.id) is not None
    assert await Group.filter(id=other.group_id).exists()
