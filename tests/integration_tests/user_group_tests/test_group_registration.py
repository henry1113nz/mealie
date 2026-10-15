from fastapi.testclient import TestClient

from mealie.repos.all_repositories import get_repositories
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.response.pagination import PaginationQuery
from tests.utils import api_routes
from tests.utils.factories import user_registration_factory
from tests.utils.seed_data import seeded_food_names, seeded_unit_names


def test_user_registration_new_group(api_client: TestClient):
    registration = user_registration_factory()

    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 201

    # Login
    form_data = {"username": registration.email, "password": registration.password}

    response = api_client.post(api_routes.auth_token, data=form_data)
    assert response.status_code == 200
    token = response.json().get("access_token")

    assert token is not None


def test_new_user_group_permissions(api_client: TestClient):
    registration = user_registration_factory()

    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 201

    # Login
    form_data = {"username": registration.email, "password": registration.password}

    response = api_client.post(api_routes.auth_token, data=form_data)
    assert response.status_code == 200
    token = response.json().get("access_token")

    assert token is not None

    # Get User

    headers = {"Authorization": f"Bearer {token}"}
    response = api_client.get(api_routes.users_self, headers=headers)

    assert response.status_code == 200
    user = response.json()

    assert user.get("canInvite") is True
    assert user.get("canManage") is True
    assert user.get("canOrganize") is True


def test_user_registration_with_seed_data(api_client: TestClient, unfiltered_database: AllRepositories):
    registration = user_registration_factory()
    registration.seed_data = True

    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 201

    group_id = response.json()["groupId"]
    group_repos = get_repositories(unfiltered_database.session, group_id=group_id)

    foods = group_repos.ingredient_foods.page_all(PaginationQuery(page=1, per_page=-1)).items
    units = group_repos.ingredient_units.page_all(PaginationQuery(page=1, per_page=-1)).items

    assert {food.name for food in foods} == seeded_food_names(registration.locale)
    assert {unit.name for unit in units} == seeded_unit_names(registration.locale)
    assert all(food.label_id is not None for food in foods)


def test_registration_rows_are_readable_by_legacy_orm(api_client: TestClient):
    from sqlalchemy import text

    from mealie.db.db_setup import session_context
    from tests.utils import api_routes

    registration = user_registration_factory()
    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 201
    body = response.json()
    group_id = body["groupId"]
    household_id = body["householdId"]

    with session_context() as session:
        group = session.execute(
            text("SELECT id, name FROM groups WHERE id = :id"), {"id": group_id.replace("-", "")}
        ).one()
        household = session.execute(
            text("SELECT id, group_id FROM households WHERE id = :id"), {"id": household_id.replace("-", "")}
        ).one()
        group_preferences = session.execute(
            text("SELECT group_id FROM group_preferences WHERE group_id = :id"),
            {"id": group_id.replace("-", "")},
        ).one()
        household_preferences = session.execute(
            text("SELECT household_id FROM household_preferences WHERE household_id = :id"),
            {"id": household_id.replace("-", "")},
        ).one()
        ai_settings = session.execute(
            text("SELECT group_id FROM ai_provider_settings WHERE group_id = :id"),
            {"id": group_id.replace("-", "")},
        ).one()

    assert group.name == registration.group
    assert group.id == group_preferences.group_id == ai_settings.group_id
    assert household.id == household_preferences.household_id
    assert household.group_id == group.id

    token_response = api_client.post(
        api_routes.auth_token,
        data={"username": registration.username, "password": registration.password},
    )
    assert token_response.status_code == 200
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
    legacy_group_response = api_client.get(api_routes.groups_self, headers=headers)
    assert legacy_group_response.status_code == 200
    assert legacy_group_response.json()["id"] == group_id
