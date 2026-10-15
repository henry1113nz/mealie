import random
import string

from fastapi.testclient import TestClient

from mealie.core.config import get_app_settings
from tests.utils import api_routes
from tests.utils.factories import user_registration_factory


def test_register_user(api_client: TestClient, monkeypatch):
    # create random registration
    registration = user_registration_factory()

    # signup disabled but valid request
    monkeypatch.setenv("ALLOW_SIGNUP", "False")
    get_app_settings.cache_clear()
    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 403

    # signup disabled, request includes non valid group token
    registration.group_token = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10)).strip()
    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 400

    # signup enabled but contains non valid group token
    monkeypatch.setenv("ALLOW_SIGNUP", "True")
    get_app_settings.cache_clear()
    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 400

    # signup enabled and valid request
    registration.group_token = None
    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 201


def test_registration_rolls_back_group_household_preferences_and_user(api_client: TestClient, monkeypatch):
    from sqlalchemy import text

    from mealie.db.db_setup import session_context
    from mealie.repos.tortoise_user import TortoiseUserRepository

    registration = user_registration_factory()
    group_name = registration.group
    email = registration.email
    original_create = TortoiseUserRepository.create

    async def create_then_fail(self, data, *, connection=None):
        await original_create(self, data, connection=connection)
        raise RuntimeError("injected registration failure")

    monkeypatch.setattr(TortoiseUserRepository, "create", create_then_fail)
    monkeypatch.setattr(api_client._transport, "raise_server_exceptions", False)
    response = api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))
    assert response.status_code == 500

    with session_context() as session:
        group_id = session.execute(text("SELECT id FROM groups WHERE name = :name"), {"name": group_name}).scalar()
        assert group_id is None
        assert session.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).scalar() is None
        assert (
            session.execute(
                text("SELECT id FROM group_preferences WHERE group_id IN (SELECT id FROM groups WHERE name = :name)"),
                {"name": group_name},
            ).scalar()
            is None
        )
        assert (
            session.execute(
                text(
                    "SELECT id FROM ai_provider_settings WHERE group_id IN (SELECT id FROM groups WHERE name = :name)"
                ),
                {"name": group_name},
            ).scalar()
            is None
        )
        assert (
            session.execute(
                text("SELECT id FROM households WHERE group_id IN (SELECT id FROM groups WHERE name = :name)"),
                {"name": group_name},
            ).scalar()
            is None
        )


def test_concurrent_invite_redemption_consumes_one_use(api_client: TestClient, admin_user):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import text

    from mealie.db.db_setup import session_context

    invite_response = api_client.post(
        api_routes.households_invitations,
        json={"uses": 1},
        headers=admin_user.token,
    )
    assert invite_response.status_code == 201
    invite_token = invite_response.json()["token"]

    registrations = [user_registration_factory(), user_registration_factory()]
    for registration in registrations:
        registration.group = ""
        registration.household = ""
        registration.group_token = invite_token

    def redeem(registration):
        return api_client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(redeem, registrations))

    assert sorted(response.status_code for response in responses) == [201, 400]
    with session_context() as session:
        users = session.execute(
            text("SELECT email FROM users WHERE email IN (:email_one, :email_two)"),
            {"email_one": registrations[0].email, "email_two": registrations[1].email},
        ).all()
        invite = session.execute(
            text("SELECT uses_left FROM invite_tokens WHERE token = :token"), {"token": invite_token}
        ).scalar()

    assert len(users) == 1
    assert invite is None


def test_registration_fails_closed_without_application_lifespan():
    from fastapi import FastAPI

    from mealie.routes.users.registration import router as registration_router

    test_app = FastAPI()
    test_app.include_router(registration_router, prefix="/api/users")
    registration = user_registration_factory()

    with TestClient(test_app) as client:
        response = client.post(api_routes.users_register, json=registration.model_dump(by_alias=True))

    assert response.status_code == 503
    assert response.json() == {"detail": "Async database is not initialized"}
