"""Native household persistence against the unchanged Alembic database schema."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from mealie.core.settings import AppSettings
from mealie.db.models._tortoise_base import TortoiseBase
from mealie.db.models.group import Group
from mealie.db.models.household.cookbook import CookBook
from mealie.db.models.household.events import GroupEventNotifierModel, GroupEventNotifierOptionsModel
from mealie.db.models.household.household import Household
from mealie.db.models.household.household_to_recipe import HouseholdToRecipe
from mealie.db.models.household.invite_tokens import GroupInviteToken
from mealie.db.models.household.mealplan import GroupMealPlan, GroupMealPlanRules
from mealie.db.models.household.preferences import HouseholdPreferencesModel
from mealie.db.models.household.recipe_action import GroupRecipeAction
from mealie.db.models.household.shopping_list import (
    ShoppingList,
    ShoppingListExtras,
    ShoppingListItem,
    ShoppingListItemExtras,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
)
from mealie.db.models.household.webhooks import GroupWebhooksModel
from mealie.db.models.users.users import User
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.repos.all_repositories import AllRepositories
from mealie.schema.response.pagination import OrderDirection, PaginationQuery
from tests.fixtures.legacy_models._model_base import SqlAlchemyBase
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_engine as server_engine
from tests.unit_tests.test_tortoise_server import server_settings as server_settings
from tests.unit_tests.test_tortoise_users import create_native_user
from tests.unit_tests.test_tortoise_users import native_user_repositories as native_user_repositories

HOUSEHOLD_MODELS = (
    Household,
    HouseholdPreferencesModel,
    HouseholdToRecipe,
    CookBook,
    GroupInviteToken,
    GroupMealPlan,
    GroupMealPlanRules,
    GroupRecipeAction,
    GroupWebhooksModel,
    GroupEventNotifierModel,
    GroupEventNotifierOptionsModel,
    ShoppingList,
    ShoppingListItem,
    ShoppingListRecipeReference,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListExtras,
    ShoppingListItemExtras,
)


@pytest.mark.asyncio
async def test_household_registry_storage_metadata_and_native_relations(server_settings: AppSettings) -> None:
    config = get_tortoise_config(server_settings)
    # Preserve the original C5 registry view; runtime exercises the full native registry.
    config["apps"]["models"]["models"] = config["apps"]["models"]["models"][:19]
    assert config["apps"]["models"]["models"][9:] == [
        "mealie.db.models.household.household",
        "mealie.db.models.household.preferences",
        "mealie.db.models.household.cookbook",
        "mealie.db.models.household.events",
        "mealie.db.models.household.household_to_recipe",
        "mealie.db.models.household.invite_tokens",
        "mealie.db.models.household.mealplan",
        "mealie.db.models.household.recipe_action",
        "mealie.db.models.household.shopping_list",
        "mealie.db.models.household.webhooks",
    ]
    config["apps"]["models"]["models"].append("unused.module")
    assert "unused.module" not in get_tortoise_config(server_settings)["apps"]["models"]["models"]
    async with database_context(get_tortoise_config(server_settings)) as context:
        for model in HOUSEHOLD_MODELS:
            assert issubclass(model, TortoiseBase)
            assert context.get_model("models", model.__name__) is model
            assert model._meta.db is context.db()
            legacy = SqlAlchemyBase.metadata.tables[model._meta.db_table]
            assert set(model._meta.fields_db_projection.values()) == set(legacy.c.keys())
            for field_name, column in model._meta.fields_db_projection.items():
                assert model._meta.fields_map[field_name].null == legacy.c[column].nullable
        group = await Group.create(name="Relations")
        household = await Household.create(group_id=group.id, name="Household")
        user = await User.create(group_id=group.id, household_id=household.id, username="member")
        assert (await user.household).id == household.id
        assert (await household.group).id == group.id
        assert [row.id for row in await household.users] == [user.id]
        assert [row.id for row in await group.households] == [household.id]


@pytest.mark.asyncio
async def test_household_uuid_utc_defaults_nullability_and_constraints(
    server_settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = datetime(2026, 5, 6, tzinfo=UTC)
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: created)
    async with database_context(get_tortoise_config(server_settings)) as context:
        group = await Group.create(name="Storage")
        household = await Household.create(group_id=group.id, name="name" * 1000, slug=None)
        assert household.created_at == created
        assert household.slug is None
        preferences = await HouseholdPreferencesModel.create(household_id=household.id)
        assert preferences.private_household is True
        assert preferences.recipe_disable_amount is True
        assert preferences.recipe_show_nutrition is False
        assert preferences.first_day_of_week == 0
        preferences.private_household = None
        await preferences.save()
        assert (await HouseholdPreferencesModel.get(id=preferences.id)).private_household is None
        token = await GroupInviteToken.create(group_id=group.id, household_id=household.id, token="token" * 1000)
        assert token.uses_left == 1
        assert (await token.household).id == household.id
        with pytest.raises(IntegrityError):
            await GroupInviteToken.create(token=token.token)
        with pytest.raises(IntegrityError):
            await Household.create(group_id=group.id, name=household.name)
        with pytest.raises(IntegrityError):
            await Household.create(group_id=uuid4(), name="Invalid")
        with pytest.raises(IntegrityError):
            await HouseholdPreferencesModel.create(household_id=uuid4())
        stored = await context.db().execute_query_dict("SELECT * FROM households WHERE id = ?", [household.id.hex])
        assert stored[0]["group_id"] == group.id.hex
        assert datetime.fromisoformat(stored[0]["created_at"]) == created.replace(tzinfo=None)
        changed = created + timedelta(days=1)
        monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: changed)
        household.name = "Changed"
        await household.save(update_fields=["name", "update_at"])
        assert (await Household.get(id=household.id)).updated_at == changed
        list_item = await ShoppingListItem.create(note="note" * 1000)
        assert list_item.shopping_list_id is None
        assert list_item.quantity == 1


@pytest.mark.asyncio
async def test_household_repository_slug_hydration_filters_and_preferences(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    household = (await repos.households.get_all())[0]
    preferences = await repos.household_preferences.create({"household_id": household.id})
    assert (await repos.households.get_by_slug_or_id(household.slug)).preferences == preferences
    assert await other.household_preferences.get_one(household.id) is None
    assert await other.households.get_one(household.id) is None
    duplicates = await repos.households.create_many([{"name": "Same"}, {"name": "Same"}])
    assert [row.name for row in duplicates] == ["Same", "Same (1)"]
    assert [row.slug for row in duplicates] == ["same", "same-1"]
    page = await repos.households.page_all(PaginationQuery(query_filter=f"id={household.id}", order_by="name"))
    assert [row.id for row in page.items] == [household.id]
    renamed = await repos.households.update(household.id, {"name": "New Name"})
    assert renamed.slug == "new-name"
    with pytest.raises(RuntimeError, match="rollback"):
        async with in_transaction("default"):
            await repos.household_preferences.patch(household.id, {"private_household": False})
            raise RuntimeError("rollback")
    assert (await repos.household_preferences.get_one(household.id)).private_household is True


@pytest.mark.asyncio
async def test_household_notifications_nested_options_and_transactional_cleanup(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    household = (await repos.households.get_all())[0]
    notifier = await repos.group_event_notifier.create(
        {
            "group_id": repos.group_id,
            "household_id": household.id,
            "name": "Events",
            "apprise_url": "json://example.test",
            "options": {"recipe_created": True},
        }
    )
    assert notifier.options.recipe_created is True
    assert notifier.options.recipe_updated is False
    assert await other.group_event_notifier.get_one(notifier.id) is None
    changed = await repos.group_event_notifier.update(notifier.id, {"options": {"recipe_updated": True}})
    assert changed.options.recipe_updated is True
    assert await GroupEventNotifierOptionsModel.filter(event_notifier_id=notifier.id).count() == 1
    with pytest.raises(RuntimeError, match="rollback"):
        async with in_transaction("default"):
            await repos.group_event_notifier.delete(notifier.id)
            assert not await GroupEventNotifierOptionsModel.filter(event_notifier_id=notifier.id).exists()
            raise RuntimeError("rollback")
    assert await GroupEventNotifierModel.filter(id=notifier.id).exists()
    await repos.group_event_notifier.delete(notifier.id)
    assert not await GroupEventNotifierOptionsModel.filter(event_notifier_id=notifier.id).exists()


@pytest.mark.asyncio
async def test_shopping_list_nested_extras_scope_replacement_and_rollback(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    user = await create_native_user(repos, "shopping-owner")
    shopping_list = await repos.group_shopping_lists.create(
        {
            "group_id": repos.group_id,
            "user_id": user.id,
            "name": "List",
            "extras": {"aisle": "A"},
        }
    )
    item = await repos.group_shopping_list_item.create(
        {
            "shopping_list_id": shopping_list.id,
            "note": "Apples",
            "quantity": 3,
            "extras": {"shop": "B"},
        }
    )
    hydrated = await repos.group_shopping_lists.get_one(shopping_list.id)
    assert hydrated.extras == {"aisle": "A"}
    assert hydrated.list_items[0].extras == {"shop": "B"}
    assert hydrated.list_items[0].household_id == user.household_id
    assert await other.group_shopping_lists.get_one(shopping_list.id) is None
    assert await other.group_shopping_list_item.get_one(item.id) is None
    assert (await other.group_shopping_list_item.page_all(PaginationQuery(per_page=-1))).items == []
    changed = await repos.group_shopping_list_item.update(item.id, {"extras": {"replacement": "C"}})
    assert changed.extras == {"replacement": "C"}
    assert await ShoppingListItemExtras.filter(shopping_list_item_id=item.id).count() == 1
    with pytest.raises(RuntimeError, match="rollback"):
        async with in_transaction("default"):
            await repos.group_shopping_lists.delete(shopping_list.id)
            assert not await ShoppingListItem.filter(id=item.id).exists()
            assert not await ShoppingListExtras.filter(shopping_list_id=shopping_list.id).exists()
            assert not await ShoppingListItemExtras.filter(shopping_list_item_id=item.id).exists()
            raise RuntimeError("rollback")
    assert await ShoppingListItem.filter(id=item.id).exists()
    await repos.group_shopping_lists.delete(shopping_list.id)
    assert not await ShoppingListItem.filter(id=item.id).exists()
    assert not await ShoppingListItemExtras.filter(shopping_list_item_id=item.id).exists()


@pytest.mark.asyncio
async def test_mealplan_proxy_scope_filtering_and_dates(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    user = await create_native_user(repos, "meal-owner")
    meal = await repos.meals.create(
        {
            "date": date(2026, 5, 6),
            "entry_type": "dinner",
            "title": "Dinner",
            "text": "Meal",
            "group_id": repos.group_id,
            "user_id": user.id,
        }
    )
    assert meal.household_id == user.household_id
    assert meal.recipe is None
    assert await other.meals.get_one(meal.id) is None
    page = await repos.meals.page_all(
        PaginationQuery(
            query_filter=f"household_id={user.household_id}",
            order_by="date",
            order_direction=OrderDirection.asc,
        )
    )
    assert [row.id for row in page.items] == [meal.id]
    assert page.items[0].date == date(2026, 5, 6)
    await repos.meals.delete(meal.id)
    assert not await GroupMealPlan.filter(id=meal.id).exists()


@pytest.mark.asyncio
async def test_household_deletion_clears_nullable_members_and_rolls_back(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)):
        group = await Group.create(name="Delete group")
        household = await Household.create(group_id=group.id, name="Delete household")
        user = await User.create(group_id=group.id, household_id=household.id, username="Retained")
        preference = await HouseholdPreferencesModel.create(household_id=household.id)
        cookbook = await CookBook.create(group_id=group.id, household_id=household.id, name="Book", slug="book")
        invite = await GroupInviteToken.create(group_id=group.id, household_id=household.id, token="invite")
        with pytest.raises(RuntimeError, match="rollback"):
            async with in_transaction("default"):
                await household.delete()
                assert not await HouseholdPreferencesModel.filter(id=preference.id).exists()
                assert not await CookBook.filter(id=cookbook.id).exists()
                assert not await GroupInviteToken.filter(id=invite.id).exists()
                assert (await User.get(id=user.id)).household_id is None
                raise RuntimeError("rollback")
        assert (await User.get(id=user.id)).household_id == household.id
        assert await Household.filter(id=household.id).exists()
        await household.delete()
        assert (await User.get(id=user.id)).household_id is None
        assert not await Household.filter(id=household.id).exists()
