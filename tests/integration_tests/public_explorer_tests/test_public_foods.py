import pytest
from fastapi.testclient import TestClient

from mealie.schema.recipe.recipe_ingredient import SaveIngredientFood
from tests.fixtures.fixture_database import run_db
from tests.utils import api_routes
from tests.utils.factories import random_int, random_string
from tests.utils.fixture_schemas import TestUser


@pytest.mark.parametrize("is_private_group", [True, False])
@pytest.mark.parametrize("is_private_household", [True, False])
def test_get_all_foods(
    api_client: TestClient,
    unique_user: TestUser,
    is_private_group: bool,
    is_private_household: bool,
):
    database = unique_user.repos

    ## Set Up Group
    group = run_db(database.groups.get_one(unique_user.group_id))
    assert group and group.preferences

    group.preferences.private_group = is_private_group
    run_db(database.group_preferences.update(group.id, group.preferences))

    ## Set Up Household
    household = run_db(database.households.get_one(unique_user.household_id))
    assert household and household.preferences

    household.preferences.private_household = is_private_household
    household.preferences.recipe_public = not is_private_household
    run_db(database.household_preferences.update(household.id, household.preferences))

    ## Set Up Foods
    foods = run_db(
        database.ingredient_foods.create_many(
            [SaveIngredientFood(name=random_string(), group_id=unique_user.group_id) for _ in range(random_int(15, 20))]
        )
    )

    ## Test Foods
    response = api_client.get(api_routes.explore_groups_group_slug_foods(unique_user.group_id))

    # whether or not the household is private shouldn't affect food visibility
    if is_private_group:
        assert response.status_code == 404
        return

    assert response.status_code == 200
    foods_data = response.json()
    fetched_ids: set[str] = {food["id"] for food in foods_data["items"]}

    for food in foods:
        assert str(food.id) in fetched_ids


@pytest.mark.parametrize("is_private_group", [True, False])
@pytest.mark.parametrize("is_private_household", [True, False])
def test_get_one_food(
    api_client: TestClient,
    unique_user: TestUser,
    is_private_group: bool,
    is_private_household: bool,
):
    database = unique_user.repos

    ## Set Up Group
    group = run_db(database.groups.get_one(unique_user.group_id))
    assert group and group.preferences

    group.preferences.private_group = is_private_group
    run_db(database.group_preferences.update(group.id, group.preferences))

    ## Set Up Household
    household = run_db(database.households.get_one(unique_user.household_id))
    assert household and household.preferences

    household.preferences.private_household = is_private_household
    household.preferences.recipe_public = not is_private_household
    run_db(database.household_preferences.update(household.id, household.preferences))

    ## Set Up Food
    food = run_db(
        database.ingredient_foods.create(SaveIngredientFood(name=random_string(), group_id=unique_user.group_id))
    )

    ## Test Food
    response = api_client.get(api_routes.explore_groups_group_slug_foods_item_id(unique_user.group_id, food.id))

    # whether or not the household is private shouldn't affect food visibility
    if is_private_group:
        assert response.status_code == 404
        return

    assert response.status_code == 200
    food_data = response.json()
    assert food_data["id"] == str(food.id)
