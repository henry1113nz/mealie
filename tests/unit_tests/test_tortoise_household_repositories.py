"""Household repository regression checks using the unchanged migration schema."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from mealie.db.models._legacy_household import ShoppingListItem as LegacyShoppingListItem
from mealie.db.models.household.shopping_list import ShoppingListItemRecipeReference
from mealie.db.models.users import User
from mealie.repos import _users_coexistence as bridge
from mealie.repos.all_repositories import AllRepositories, get_repositories
from mealie.schema.response.pagination import PaginationQuery
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_engine as server_engine
from tests.unit_tests.test_tortoise_server import server_settings as server_settings
from tests.unit_tests.test_tortoise_users import create_native_user, insert_native_recipe
from tests.unit_tests.test_tortoise_users import native_user_repositories as native_user_repositories


@pytest.mark.asyncio
@pytest.mark.parametrize("dialect", ["sqlite", "postgres"])
async def test_household_uuid_in_compilation_applies_expanded_parameter_conversion(
    monkeypatch: pytest.MonkeyPatch, dialect: str
) -> None:
    identifier = uuid4()
    connection = SimpleNamespace(
        capabilities=SimpleNamespace(dialect=dialect),
        execute_query_dict=AsyncMock(return_value=[{"id": str(identifier)}]),
    )
    monkeypatch.setattr(bridge, "connections", SimpleNamespace(get=lambda alias: connection))
    result = await bridge.query_model_ids(
        LegacyShoppingListItem, None, PaginationQuery(query_filter=f'id IN ["{identifier}"] AND checked=true')
    )
    assert result == [str(identifier)]
    sql, parameters = connection.execute_query_dict.call_args.args
    assert parameters == [identifier.hex if dialect == "sqlite" else str(identifier)]
    assert " IN (?)" in sql if dialect == "sqlite" else " IN ($1::UUID)" in sql


@pytest.mark.asyncio
async def test_household_uuid_in_filter_and_same_group_household_scoping(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, _ = native_user_repositories
    first_user = await create_native_user(repos, "first-household-owner")
    second_household = await repos.households.create({"name": "Second household"})
    second_user = await User.create(
        username="second-household-owner", group_id=repos.group_id, household_id=second_household.id
    )
    first_repos = get_repositories(repos.session, group_id=repos.group_id, household_id=first_user.household_id)
    second_repos = get_repositories(repos.session, group_id=repos.group_id, household_id=second_household.id)
    first_list = await first_repos.group_shopping_lists.create({"group_id": repos.group_id, "user_id": first_user.id})
    second_list = await second_repos.group_shopping_lists.create(
        {"group_id": repos.group_id, "user_id": second_user.id}
    )
    first_item = await first_repos.group_shopping_list_item.create(
        {"shopping_list_id": first_list.id, "checked": True, "note": "First"}
    )
    second_item = await second_repos.group_shopping_list_item.create(
        {"shopping_list_id": second_list.id, "checked": True, "note": "Second"}
    )
    query = PaginationQuery(per_page=-1, query_filter=f'id IN ["{first_item.id}", "{second_item.id}"] AND checked=true')
    assert [item.id for item in (await first_repos.group_shopping_list_item.page_all(query)).items] == [first_item.id]
    assert [item.id for item in (await second_repos.group_shopping_list_item.page_all(query)).items] == [second_item.id]
    assert await first_repos.group_shopping_lists.get_one(second_list.id) is None
    assert await second_repos.group_shopping_list_item.get_one(first_item.id) is None
    assert await first_repos.group_shopping_list_item.multi_query({"shopping_list_id": second_list.id}) == []
    assert await first_repos.group_shopping_list_item.count_all() == 1
    await first_repos.group_shopping_list_item.delete_many([second_item.id])
    assert await second_repos.group_shopping_list_item.get_one(second_item.id) is not None


@pytest.mark.asyncio
async def test_household_statistics_follow_recipe_users_and_group_owned_taxonomy(
    native_user_repositories: tuple[AllRepositories, AllRepositories], server_engine: Engine
) -> None:
    repos, other = native_user_repositories
    first_user = await create_native_user(repos, "statistics-owner")
    foreign_user = await create_native_user(other, "statistics-foreign")
    second_household = await repos.households.create({"name": "Statistics second household"})
    second_user = await User.create(
        username="statistics-second",
        full_name="Statistics second",
        email="statistics-second@example.test",
        password="stored-password",
        group_id=repos.group_id,
        household_id=second_household.id,
    )
    insert_native_recipe(server_engine, first_user)
    insert_native_recipe(server_engine, first_user)
    insert_native_recipe(server_engine, await repos.users.get_one(second_user.id))
    insert_native_recipe(server_engine, foreign_user)
    await repos.categories.create({"name": "Owned category", "group_id": repos.group_id})
    await repos.tags.create({"name": "Owned tag", "group_id": repos.group_id})
    await repos.tools.create({"name": "Owned tool", "group_id": repos.group_id})
    await other.categories.create({"name": "Other category", "group_id": other.group_id})
    statistics = await repos.households.statistics(first_user.group_id, first_user.household_id)
    assert statistics.total_recipes == 2
    assert statistics.total_users == 1
    assert statistics.total_categories == 1
    assert statistics.total_tags == 1
    assert statistics.total_tools == 1
    second = await repos.households.statistics(first_user.group_id, second_household.id)
    assert second.total_recipes == 1
    assert second.total_users == 1
    assert second.total_categories == 1


@pytest.mark.asyncio
async def test_shopping_item_nested_identity_replacement_and_foreign_child_rollback(
    native_user_repositories: tuple[AllRepositories, AllRepositories], server_engine: Engine
) -> None:
    repos, _ = native_user_repositories
    user = await create_native_user(repos, "nested-owner")
    recipe_id = insert_native_recipe(server_engine, user)
    shopping_list = await repos.group_shopping_lists.create({"group_id": repos.group_id, "user_id": user.id})
    first_item = await repos.group_shopping_list_item.create(
        {
            "shopping_list_id": shopping_list.id,
            "note": "Original",
            "extras": {"original": "yes"},
            "recipe_references": [{"recipe_id": recipe_id, "recipe_quantity": 2, "recipe_scale": 1}],
        }
    )
    second_item = await repos.group_shopping_list_item.create(
        {
            "shopping_list_id": shopping_list.id,
            "note": "Other",
            "recipe_references": [{"recipe_id": recipe_id, "recipe_quantity": 3, "recipe_scale": 2}],
        }
    )
    original_ref = first_item.recipe_references[0]
    foreign_ref = second_item.recipe_references[0]
    with pytest.raises(ValueError, match="does not belong"):
        await repos.group_shopping_list_item.update(
            first_item.id,
            {
                "note": "Must roll back",
                "extras": {"changed": "no"},
                "recipe_references": [foreign_ref.model_dump()],
            },
        )
    unchanged = await repos.group_shopping_list_item.get_one(first_item.id)
    assert unchanged.note == "Original"
    assert unchanged.extras == {"original": "yes"}
    assert unchanged.recipe_references == [original_ref]
    assert (await ShoppingListItemRecipeReference.get(id=foreign_ref.id)).shopping_list_item_id == second_item.id
    changed = await repos.group_shopping_list_item.update(
        first_item.id, {"recipe_references": [{**original_ref.model_dump(), "recipe_scale": 5}]}
    )
    assert len(changed.recipe_references) == 1
    assert changed.recipe_references[0].id == original_ref.id
    assert changed.recipe_references[0].recipe_scale == 5
    cleared = await repos.group_shopping_list_item.update(first_item.id, {"recipe_references": []})
    assert cleared.recipe_references == []
    assert not await ShoppingListItemRecipeReference.filter(id=original_ref.id).exists()
    assert await ShoppingListItemRecipeReference.filter(id=foreign_ref.id).exists()
