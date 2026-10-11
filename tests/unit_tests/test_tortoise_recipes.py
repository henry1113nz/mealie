"""Native recipe models against the unchanged production Alembic schema."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from mealie.core.settings import AppSettings
from mealie.db.models._tortoise_base import TortoiseBase, UUIDField
from mealie.db.models.group import Group
from mealie.db.models.household import (
    CookBook,
    GroupMealPlanRules,
    Household,
    HouseholdToRecipe,
    ShoppingList,
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
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from tests.fixtures.legacy_models._model_base import SqlAlchemyBase
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_settings as server_settings

RECIPE_MODELS = (
    ApiExtras,
    IngredientFoodExtras,
    RecipeAsset,
    Category,
    RecipeComment,
    IngredientFoodAliasModel,
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    IngredientUnitAliasModel,
    IngredientUnitModel,
    RecipeIngredientModel,
    RecipeIngredientSubstitutionModel,
    RecipeIngredientRefLink,
    RecipeInstruction,
    RecipeNoteRefLink,
    MultiPurposeLabel,
    Note,
    Nutrition,
    RecipeModel,
    RecipeTimelineEvent,
    RecipeSettings,
    RecipeShareTokenModel,
    Tag,
    Tool,
)


@pytest.mark.asyncio
async def test_recipe_registry_column_nullability_indexes_and_uuid_relations(server_settings: AppSettings) -> None:
    config = get_tortoise_config(server_settings)
    assert len(config["apps"]["models"]["models"][19:]) == 15
    assert len(RECIPE_MODELS) == 24
    async with database_context(config) as context:
        for model in RECIPE_MODELS:
            assert issubclass(model, TortoiseBase)
            assert context.get_model("models", model.__name__) is model
            assert model._meta.db is context.db()
            legacy = SqlAlchemyBase.metadata.tables[model._meta.db_table]
            assert set(model._meta.fields_db_projection.values()) == set(legacy.c.keys())
            for field_name, column in model._meta.fields_db_projection.items():
                field = model._meta.fields_map[field_name]
                assert field.null == legacy.c[column].nullable
                if not legacy.c[column].primary_key:
                    assert field.index == bool(legacy.c[column].index)
                if str(legacy.c[column].type) == "CHAR(32)":
                    assert isinstance(field, UUIDField)


@pytest.mark.asyncio
async def test_recipe_storage_normalization_partial_saves_and_constraints(
    server_settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: created)
    async with database_context(get_tortoise_config(server_settings)) as context:
        group = await Group.create(name="Storage")
        recipe = await RecipeModel.create(
            group_id=group.id, name="Crème fraîche!", slug="creme", description="x" * 2000
        )
        assert recipe.name_normalized == "creme fraiche"
        assert recipe.description_normalized == "x" * 255
        assert recipe.user_id is None
        assert recipe.recipe_servings == 0
        assert recipe.created_at == created
        assert recipe.updated_at == created
        rows = await context.db().execute_query_dict("SELECT * FROM recipes WHERE id = ?", [recipe.id.hex])
        assert rows[0]["id"] == recipe.id.hex
        assert rows[0]["group_id"] == group.id.hex
        assert datetime.fromisoformat(rows[0]["created_at"]) == created.replace(tzinfo=None)
        recipe.name = "Á new-name"
        recipe.description = None
        recipe.last_made = datetime(2026, 1, 2, 3, tzinfo=timezone(timedelta(hours=2)))
        changed = created + timedelta(days=1)
        monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: changed)
        await recipe.save(update_fields=["name", "description", "last_made", "update_at"])
        saved = await RecipeModel.get(id=recipe.id)
        assert saved.name_normalized == "a new name"
        assert saved.description_normalized is None
        assert saved.last_made == datetime(2026, 1, 2, 1, tzinfo=UTC)
        assert saved.updated_at == changed
        with pytest.raises(IntegrityError):
            await RecipeModel.create(group_id=group.id, name="Duplicate", slug="creme")
        with pytest.raises(IntegrityError):
            await RecipeModel.create(group_id=uuid4(), name="Missing group")
        food = await IngredientFoodModel.create(group_id=group.id, name="Crème", plural_name=None)
        assert food.name_normalized == "creme"
        assert food.plural_name_normalized is None
        alias = await IngredientFoodAliasModel.create(food_id=food.id, name="Álias")
        assert alias.name_normalized == "alias"
        with pytest.raises(IntegrityError):
            await IngredientFoodSubstitutionModel.create(food_id=food.id, substitute_food_id=food.id)
        with pytest.raises(IntegrityError):
            await IngredientFoodSubstitutionModel.create(food_id=food.id)
        with pytest.raises(IntegrityError):
            await IngredientFoodModel.create(group_id=group.id, name=food.name)
        settings = await RecipeSettings.create(recipe_id=recipe.id)
        assert settings.public is True
        assert settings.disable_comments is False
        assert settings.locked is False


@pytest.mark.asyncio
async def test_recipe_native_cross_domain_relationships(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)):
        group = await Group.create(name="Relations")
        household = await Household.create(group_id=group.id, name="Household")
        user = await User.create(group_id=group.id, household_id=household.id, username="member")
        recipe = await RecipeModel.create(group_id=group.id, user_id=user.id, name="Recipe")
        category = await Category.create(group_id=group.id, name=" Category ")
        tag = await Tag.create(group_id=group.id, name="Tag")
        tool = await Tool.create(group_id=group.id, name="Tool")
        food = await IngredientFoodModel.create(group_id=group.id, name="Food")
        await recipe.recipe_category.add(category)
        await recipe.tags.add(tag)
        await recipe.tools.add(tool)
        await category.groups.add(group)
        await tool.households_with_tool.add(household)
        await food.households_with_ingredient_food.add(household)
        cookbook = await CookBook.create(group_id=group.id, household_id=household.id, name="Book", slug="book")
        rule = await GroupMealPlanRules.create(group_id=group.id, household_id=household.id)
        await cookbook.categories.add(category)
        await cookbook.tags.add(tag)
        await cookbook.tools.add(tool)
        await rule.categories.add(category)
        await rule.tags.add(tag)
        rating = await UserToRecipe.create(user_id=user.id, recipe_id=recipe.id, rating=5, is_favorite=True)
        made = await HouseholdToRecipe.create(household_id=household.id, recipe_id=recipe.id)
        user.owned_recipes_id = recipe.id
        await user.save(update_fields=["owned_recipes_id", "update_at"])
        assert (await recipe.group).id == group.id
        assert (await recipe.user).id == user.id
        assert (await rating.recipe).id == recipe.id
        assert (await made.recipe).id == recipe.id
        assert (await user.owned_recipes).id == recipe.id
        assert [row.id for row in await category.recipes] == [recipe.id]
        assert [row.id for row in await group.categories] == [category.id]
        assert [row.id for row in await household.tools_on_hand] == [tool.id]
        assert [row.id for row in await household.ingredient_foods_on_hand] == [food.id]
        assert [row.id for row in await cookbook.categories] == [category.id]
        assert [row.id for row in await rule.tags] == [tag.id]
        assert category.name == "Category"
        assert category.slug == "category"


@pytest.mark.asyncio
async def test_recipe_delete_rolls_back_and_preserves_referring_objects(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)):
        group = await Group.create(name="Delete")
        other_group = await Group.create(name="Other")
        user = await User.create(group_id=other_group.id, username="member")
        recipe = await RecipeModel.create(group_id=group.id, name="Deleted")
        other = await RecipeModel.create(group_id=other_group.id, user_id=user.id, name="Retained")
        user.owned_recipes_id = recipe.id
        await user.save()
        ingredient = await RecipeIngredientModel.create(recipe_id=recipe.id, note="ingredient")
        await RecipeIngredientSubstitutionModel.create(ingredient_id=ingredient.id, note="workaround")
        reference = await RecipeIngredientModel.create(recipe_id=other.id, referenced_recipe_id=recipe.id)
        instruction = await RecipeInstruction.create(recipe_id=recipe.id, text="step")
        link = await RecipeIngredientRefLink.create(instruction_id=instruction.id, reference_id=uuid4())
        await RecipeNoteRefLink.create(instruction_id=instruction.id, reference_id=uuid4())
        await RecipeComment.create(recipe_id=recipe.id, user_id=user.id, text="Comment")
        await RecipeTimelineEvent.create(recipe_id=recipe.id, user_id=user.id, subject="Event")
        await RecipeSettings.create(recipe_id=recipe.id)
        await Nutrition.create(recipe_id=recipe.id, calories="10")
        await RecipeAsset.create(recipe_id=recipe.id, name="asset")
        await Note.create(recipe_id=recipe.id, title="note", text="text")
        await ApiExtras.create(recipee_id=recipe.id, key_name="key", value="value")
        await UserToRecipe.create(user_id=user.id, recipe_id=recipe.id, rating=5, is_favorite=True)
        listing = await ShoppingList.create(group_id=other_group.id, user_id=user.id)
        item = await ShoppingListItem.create(shopping_list_id=listing.id)
        await ShoppingListRecipeReference.create(shopping_list_id=listing.id, recipe_id=recipe.id, recipe_quantity=1)
        await ShoppingListItemRecipeReference.create(
            shopping_list_item_id=item.id, recipe_id=recipe.id, recipe_quantity=1
        )
        with pytest.raises(RuntimeError, match="rollback"):
            async with in_transaction("default"):
                await recipe.delete()
                assert not await RecipeModel.filter(id=recipe.id).exists()
                assert (await RecipeIngredientModel.get(id=reference.id)).referenced_recipe_id is None
                raise RuntimeError("rollback")
        assert await RecipeModel.filter(id=recipe.id).exists()
        assert await RecipeIngredientRefLink.filter(id=link.id).exists()
        assert (await RecipeIngredientModel.get(id=reference.id)).referenced_recipe_id == recipe.id
        await recipe.delete()
        assert not await RecipeIngredientModel.filter(recipe_id=recipe.id).exists()
        assert not await RecipeIngredientSubstitutionModel.filter(ingredient_id=ingredient.id).exists()
        assert not await RecipeIngredientRefLink.filter(id=link.id).exists()
        assert not await RecipeComment.filter(recipe_id=recipe.id).exists()
        assert not await UserToRecipe.filter(recipe_id=recipe.id).exists()
        assert not await ShoppingListRecipeReference.filter(recipe_id=recipe.id).exists()
        assert not await ShoppingListItemRecipeReference.filter(recipe_id=recipe.id).exists()
        assert await RecipeModel.filter(id=other.id).exists()
        assert await ShoppingListItem.filter(id=item.id).exists()
        assert await ShoppingList.filter(id=listing.id).exists()
        assert (await User.get(id=user.id)).owned_recipes_id is None
        assert (await RecipeIngredientModel.get(id=reference.id)).referenced_recipe_id is None


@pytest.mark.asyncio
async def test_recipe_group_delete_cleans_cross_group_references_and_associations(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)):
        group = await Group.create(name="Delete")
        other_group = await Group.create(name="Other")
        household = await Household.create(group_id=other_group.id, name="Household")
        user = await User.create(group_id=other_group.id, household_id=household.id, username="member")
        recipe = await RecipeModel.create(group_id=group.id, name="Deleted")
        other = await RecipeModel.create(group_id=other_group.id, user_id=user.id, name="Retained")
        label = await MultiPurposeLabel.create(group_id=group.id, name="Label")
        food = await IngredientFoodModel.create(group_id=group.id, name="Food", label_id=label.id)
        other_food = await IngredientFoodModel.create(group_id=other_group.id, name="Other food", label_id=label.id)
        unit = await IngredientUnitModel.create(group_id=group.id, name="Unit")
        await IngredientUnitAliasModel.create(unit_id=unit.id, name="Unit alias")
        await IngredientFoodAliasModel.create(food_id=food.id, name="Food alias")
        await IngredientFoodExtras.create(ingredient_food_id=food.id, key_name="key", value="value")
        await IngredientFoodSubstitutionModel.create(food_id=other_food.id, substitute_food_id=food.id)
        ingredient = await RecipeIngredientModel.create(
            recipe_id=other.id, referenced_recipe_id=recipe.id, food_id=food.id, unit_id=unit.id
        )
        await RecipeIngredientSubstitutionModel.create(ingredient_id=ingredient.id, substitute_food_id=food.id)
        category = await Category.create(group_id=group.id, name="Category")
        tag = await Tag.create(group_id=group.id, name="Tag")
        tool = await Tool.create(group_id=group.id, name="Tool")
        await other.recipe_category.add(category)
        await other.tags.add(tag)
        await other.tools.add(tool)
        await household.tools_on_hand.add(tool)
        await household.ingredient_foods_on_hand.add(food)
        await other_group.categories.add(category)
        listing = await ShoppingList.create(group_id=other_group.id, user_id=user.id)
        item = await ShoppingListItem.create(
            shopping_list_id=listing.id, food_id=food.id, unit_id=unit.id, label_id=label.id
        )
        await ShoppingListMultiPurposeLabel.create(shopping_list_id=listing.id, label_id=label.id)
        with pytest.raises(RuntimeError, match="rollback"):
            async with in_transaction("default"):
                await group.delete()
                raise RuntimeError("rollback")
        assert await IngredientFoodModel.filter(id=food.id).exists()
        assert [row.id for row in await household.tools_on_hand] == [tool.id]
        assert (await ShoppingListItem.get(id=item.id)).food_id == food.id
        await group.delete()
        assert not await Group.filter(id=group.id).exists()
        assert not await RecipeModel.filter(id=recipe.id).exists()
        assert await RecipeModel.filter(id=other.id).exists()
        assert await IngredientFoodModel.filter(id=other_food.id).exists()
        assert (await IngredientFoodModel.get(id=other_food.id)).label_id is None
        assert not await IngredientFoodSubstitutionModel.filter(food_id=other_food.id).exists()
        assert not await RecipeIngredientSubstitutionModel.filter(ingredient_id=ingredient.id).exists()
        saved = await RecipeIngredientModel.get(id=ingredient.id)
        assert saved.food_id is None
        assert saved.unit_id is None
        assert saved.referenced_recipe_id is None
        saved_item = await ShoppingListItem.get(id=item.id)
        assert saved_item.food_id is None
        assert saved_item.unit_id is None
        assert saved_item.label_id is None
        assert not await ShoppingListMultiPurposeLabel.filter(shopping_list_id=listing.id).exists()
        assert not await other.recipe_category.all()
        assert not await other.tags.all()
        assert not await other.tools.all()
        assert not await household.tools_on_hand.all()
        assert not await household.ingredient_foods_on_hand.all()
        assert not await other_group.categories.all()
