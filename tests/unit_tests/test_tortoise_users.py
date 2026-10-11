from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import Engine, insert, text
from sqlalchemy.orm import Session
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.transactions import in_transaction

from mealie.core.settings import AppSettings
from mealie.db.models._legacy_household.mealplan import GroupMealPlan
from mealie.db.models._legacy_household.shopping_list import ShoppingList, ShoppingListItem
from mealie.db.models.recipe.api_extras import ShoppingListExtras, ShoppingListItemExtras
from mealie.db.models.recipe.comment import RecipeComment
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.recipe_timeline import RecipeTimelineEvent
from mealie.db.models.server.task import ServerTaskModel
from mealie.db.models.users.password_reset import PasswordResetModel
from mealie.db.models.users.user_to_recipe import UserToRecipe
from mealie.db.models.users.users import AuthMethod, LongLiveToken, User
from mealie.db.tortoise_config import TORTOISE_MODEL_MODULES, get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.repos import _users_coexistence as bridge
from mealie.repos.all_repositories import AllRepositories, get_repositories
from mealie.schema.response.pagination import OrderByNullPosition, OrderDirection, PaginationQuery
from mealie.schema.user.user import PrivateUser
from tests.unit_tests.test_tortoise_server import (
    create_group,
)
from tests.unit_tests.test_tortoise_server import (
    migrated_server_database as migrated_server_database,
)
from tests.unit_tests.test_tortoise_server import (
    server_engine as server_engine,
)
from tests.unit_tests.test_tortoise_server import (
    server_settings as server_settings,
)


@pytest_asyncio.fixture
async def native_user_repositories(
    server_settings: AppSettings, server_engine: Engine
) -> AsyncGenerator[tuple[AllRepositories, AllRepositories]]:
    with Session(server_engine) as session:
        async with database_context(get_tortoise_config(server_settings)):
            unfiltered = get_repositories(session, group_id=None, household_id=None)
            repositories = []
            for index in range(2):
                group = await unfiltered.groups.create({"name": f"Native group {index}"})
                repos = get_repositories(session, group_id=group.id, household_id=None)
                await repos.households.create({"name": f"Native household {index}", "group_id": group.id})
                repositories.append(repos)
            yield repositories[0], repositories[1]


async def create_native_user(repos: AllRepositories, name: str) -> PrivateUser:
    group = await repos.groups.get_one(repos.group_id)
    household = (await repos.households.get_all())[0]
    return await repos.users.create(
        {
            "username": name,
            "full_name": name,
            "email": f"{name}@example.test",
            "password": "stored-password",
            "group": group.name,
            "household": household.name,
            "admin": False,
        }
    )


def insert_native_recipe(engine: Engine, user: PrivateUser) -> UUID:
    recipe_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            insert(RecipeModel).values(
                id=recipe_id,
                group_id=user.group_id,
                user_id=user.id,
                name="Native recipe",
                name_normalized="native recipe",
            )
        )
    return recipe_id


@pytest.mark.asyncio
async def test_user_models_are_registered_with_the_default_connection(
    server_settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Preserve the original C3 registry assertions; C4 tests the expanded registry.
    monkeypatch.setattr("mealie.db.tortoise_config.TORTOISE_MODEL_MODULES", TORTOISE_MODEL_MODULES[:4])
    config = get_tortoise_config(server_settings)
    assert config["apps"] == {
        "models": {
            "models": [
                "mealie.db.models.server.task",
                "mealie.db.models.users.users",
                "mealie.db.models.users.password_reset",
                "mealie.db.models.users.user_to_recipe",
            ],
            "default_connection": "default",
        }
    }
    config["apps"]["models"]["models"].append("unused.module")
    fresh_config = get_tortoise_config(server_settings)
    assert "unused.module" not in fresh_config["apps"]["models"]["models"]
    fresh_config["apps"]["models"]["models"] = list(TORTOISE_MODEL_MODULES)
    async with database_context(fresh_config) as context:
        for model in (ServerTaskModel, User, LongLiveToken, PasswordResetModel, UserToRecipe):
            assert context.get_model("models", model.__name__) is model
            assert model._meta.db is context.db()


@pytest.mark.asyncio
async def test_user_crud_retains_uuid_enum_and_utc_storage(
    server_settings: AppSettings, server_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    group_id = create_group(server_engine)
    created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    locked = datetime(2026, 1, 2, 7, 4, 5, tzinfo=timezone(timedelta(hours=4)))
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: created)
    async with database_context(get_tortoise_config(server_settings)):
        user = await User.create(
            full_name="name" * 1000,
            username="username" * 1000,
            password="password" * 1000,
            group_id=group_id,
            auth_method=AuthMethod.MEALIE,
            locked_at=locked,
        )
        assert isinstance(user.id, UUID)
        assert user.created_at == created
        assert user.updated_at == created
        assert user.household_id is None
        assert user.email is None
        saved = await User.get(id=user.id)
        assert saved.full_name == "name" * 1000
        assert saved.username == "username" * 1000
        assert saved.password == "password" * 1000
        assert saved.auth_method is AuthMethod.MEALIE
        assert saved.locked_at == created

        with server_engine.connect() as connection:
            row = connection.execute(
                text("SELECT id, group_id, auth_method, locked_at FROM users WHERE id = :id"), {"id": user.id.hex}
            ).one()
            assert row.id == user.id.hex
            assert row.group_id == group_id.hex
            assert row.auth_method == "MEALIE"
            assert datetime.fromisoformat(row.locked_at) == created.replace(tzinfo=None)

        updated = created + timedelta(days=1)
        monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: updated)
        saved.auth_method = AuthMethod.OIDC
        saved.locked_at = None
        await saved.save(update_fields=["auth_method", "locked_at", "update_at"])
        saved = await User.get(id=user.id)
        assert saved.auth_method is AuthMethod.OIDC
        assert saved.locked_at is None
        assert saved.created_at == created
        assert saved.updated_at == updated
        await saved.delete()
        assert not await User.filter(id=user.id).exists()


@pytest.mark.asyncio
async def test_user_relations_preserve_constraints_and_transaction_rollback(
    server_settings: AppSettings, server_engine: Engine
) -> None:
    group_id = create_group(server_engine)
    async with database_context(get_tortoise_config(server_settings)):
        user = await User.create(group_id=group_id, username="native-user")
        recipe_id = uuid4()
        with server_engine.begin() as connection:
            connection.execute(
                insert(RecipeModel).values(
                    id=recipe_id,
                    group_id=group_id,
                    user_id=user.id,
                    name="Native rating",
                    name_normalized="native rating",
                    description_normalized="",
                )
            )

        token = await LongLiveToken.create(name="name" * 1000, token="token" * 1000, user_id=user.id)
        reset = await PasswordResetModel.create(token="reset", user_id=user.id)
        rating = await UserToRecipe.create(user_id=user.id, recipe_id=recipe_id, rating=4.5, is_favorite=True)
        assert (await token.user).id == user.id
        assert (await reset.user).id == user.id
        assert (await rating.user).id == user.id
        assert (await UserToRecipe.get(id=rating.id)).rating == 4.5
        assert len(await user.tokens) == 1
        assert len(await user.password_reset_tokens) == 1
        assert len(await user.ratings) == 1

        with pytest.raises(IntegrityError):
            await UserToRecipe.create(user_id=user.id, recipe_id=recipe_id, rating=2, is_favorite=False)
        with pytest.raises(IntegrityError):
            await PasswordResetModel.create(token="reset", user_id=user.id)
        with pytest.raises(IntegrityError):
            await LongLiveToken.create(name="invalid", token="invalid", user_id=uuid4())
        with pytest.raises(IntegrityError):
            await User.create(group_id=uuid4(), username="invalid-group")

        with pytest.raises(RuntimeError, match="rollback native user changes"):
            async with in_transaction("default"):
                await User.filter(id=user.id).update(username="changed", update_at=datetime.now(UTC))
                await LongLiveToken.filter(id=token.id).delete()
                await PasswordResetModel.filter(id=reset.id).delete()
                await UserToRecipe.filter(id=rating.id).delete()
                raise RuntimeError("rollback native user changes")
        assert (await User.get(id=user.id)).username == "native-user"
        assert await LongLiveToken.filter(id=token.id).exists()
        assert await PasswordResetModel.filter(id=reset.id).exists()
        assert await UserToRecipe.filter(id=rating.id).exists()
        nullable_token = await LongLiveToken.create(name="detached", token="detached")
        assert nullable_token.user_id is None


@pytest.mark.asyncio
async def test_native_user_repositories_scope_reads_and_writes_and_hydrate_relations(
    native_user_repositories: tuple[AllRepositories, AllRepositories], server_engine: Engine
) -> None:
    first, second = native_user_repositories
    entries = []
    for index, repos in enumerate((first, second)):
        user = await create_native_user(repos, f"scoped-{index}")
        recipe_id = insert_native_recipe(server_engine, user)
        token = await repos.api_tokens.create({"user_id": user.id, "name": f"API {index}", "token": f"api-{index}"})
        reset = await repos.tokens_pw_reset.create({"user_id": user.id, "token": f"reset-{index}"})
        rating = await repos.user_ratings.create(
            {"user_id": user.id, "recipe_id": recipe_id, "rating": 4, "is_favorite": True}
        )
        entries.append({"users": user, "api_tokens": token, "tokens_pw_reset": reset, "user_ratings": rating})
        assert token.user.id == user.id
        assert reset.user.id == user.id
        assert reset.user.group == user.group
        assert reset.user.household == user.household
        assert reset.user.group_slug == user.group_slug
        assert reset.user.household_slug == user.household_slug
        assert [value.name for value in reset.user.tokens] == [f"API {index}"]

    for name in ("users", "api_tokens", "tokens_pw_reset", "user_ratings"):
        repo = getattr(first, name)
        owned = entries[0][name]
        foreign = entries[1][name]
        key = "token" if name == "tokens_pw_reset" else "id"
        owned_id = getattr(owned, key)
        foreign_id = getattr(foreign, key)
        assert getattr(await repo.get_one(owned_id), key) == owned_id
        assert await repo.get_one(foreign_id) is None
        assert await repo.multi_query({key: foreign_id}) == []
        assert await repo.count_all() == 1
        page = await repo.page_all(PaginationQuery(per_page=-1))
        assert page.total == 1
        assert [getattr(value, key) for value in page.items] == [owned_id]
        with pytest.raises(DoesNotExist):
            await repo.update(foreign_id, foreign)
        with pytest.raises(DoesNotExist):
            await repo.delete(foreign_id)
        assert getattr(await getattr(second, name).get_one(foreign_id), key) == foreign_id


@pytest.mark.asyncio
async def test_native_user_repository_preserves_query_filters_and_null_ordering(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    first, second = native_user_repositories
    alpha = await create_native_user(first, "alpha")
    beta = await create_native_user(first, "beta")
    unnamed = await create_native_user(first, "unnamed")
    await create_native_user(second, "other-group")
    await User.filter(id=unnamed.id).update(full_name=None, update_at=datetime.now(UTC))

    page = await first.users.page_all(
        PaginationQuery(
            per_page=-1,
            order_by="full_name",
            order_direction=OrderDirection.asc,
            order_by_null_position=OrderByNullPosition.first,
        )
    )
    assert [value.id for value in page.items] == [unnamed.id, alpha.id, beta.id]
    page = await first.users.page_all(
        PaginationQuery(
            per_page=-1,
            order_by="full_name",
            order_direction=OrderDirection.desc,
            order_by_null_position=OrderByNullPosition.last,
        )
    )
    assert [value.id for value in page.items] == [beta.id, alpha.id, unnamed.id]
    page = await first.users.page_all(PaginationQuery(query_filter='full_name = "alpha"'))
    assert [value.id for value in page.items] == [alpha.id]
    for private_field in ("email", "password"):
        with pytest.raises(HTTPException) as error:
            await first.users.page_all(PaginationQuery(query_filter=f'{private_field} = "secret"'))
        assert error.value.status_code == 400
        with pytest.raises(HTTPException) as error:
            await first.users.page_all(PaginationQuery(order_by=private_field))
        assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_native_user_delete_cascades_and_rolls_back_with_rating_recalculation(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
    server_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos, _ = native_user_repositories
    target = await create_native_user(repos, "delete-target")
    target_directory = target.directory()
    survivor = await create_native_user(repos, "delete-survivor")
    recipe_id = insert_native_recipe(server_engine, survivor)
    owned_recipe_id = insert_native_recipe(server_engine, target)
    target_rating = await repos.user_ratings.create(
        {"user_id": target.id, "recipe_id": recipe_id, "rating": 5, "is_favorite": True}
    )
    await repos.user_ratings.create({"user_id": survivor.id, "recipe_id": recipe_id, "rating": 3, "is_favorite": False})
    assert (await bridge.related_record("recipes", "id", recipe_id))["rating"] == 4
    await repos.user_ratings.update(target_rating.id, {"rating": 1})
    assert (await bridge.related_record("recipes", "id", recipe_id))["rating"] == 2
    await repos.user_ratings.delete(target_rating.id)
    assert (await bridge.related_record("recipes", "id", recipe_id))["rating"] == 3
    await repos.user_ratings.create({"user_id": target.id, "recipe_id": recipe_id, "rating": 5, "is_favorite": True})
    await repos.api_tokens.create({"user_id": target.id, "name": "target", "token": "target-api"})
    await repos.tokens_pw_reset.create({"user_id": target.id, "token": "target-reset"})
    survivor_token = await repos.api_tokens.create(
        {"user_id": survivor.id, "name": "survivor", "token": "survivor-api"}
    )
    list_id, item_id = uuid4(), uuid4()
    with server_engine.begin() as connection:
        connection.execute(insert(ShoppingList).values(id=list_id, user_id=target.id, group_id=target.group_id))
        connection.execute(insert(ShoppingListItem).values(id=item_id, shopping_list_id=list_id))
        connection.execute(insert(ShoppingListExtras).values(shopping_list_id=list_id, key_name="k", value="v"))
        connection.execute(
            insert(ShoppingListItemExtras).values(shopping_list_item_id=item_id, key_name="k", value="v")
        )
        connection.execute(insert(RecipeComment).values(user_id=target.id, recipe_id=recipe_id, text="comment"))
        connection.execute(insert(RecipeTimelineEvent).values(user_id=target.id, recipe_id=recipe_id, subject="event"))
        connection.execute(
            insert(GroupMealPlan).values(
                user_id=target.id,
                group_id=target.group_id,
                recipe_id=recipe_id,
                date=date(2026, 1, 1),
                entry_type="dinner",
                title="meal",
                text="meal",
            )
        )

    tables = (
        "users",
        "long_live_tokens",
        "password_reset_tokens",
        "users_to_recipes",
        "recipes",
        "shopping_lists",
        "shopping_list_items",
        "shopping_list_extras",
        "shopping_list_item_extras",
        "recipe_comments",
        "recipe_timeline_events",
        "group_meal_plans",
    )

    async def snapshot() -> dict[str, list[dict[str, Any]]]:
        return {table: await bridge.execute(f'SELECT * FROM "{table}" ORDER BY id') for table in tables}

    before = await snapshot()
    original_delete = bridge.delete_user_dependents

    async def fail_after_deleting_dependents(user_id: UUID) -> None:
        await original_delete(user_id)
        raise RuntimeError("abort native cascade")

    with monkeypatch.context() as patch:
        patch.setattr(bridge, "delete_user_dependents", fail_after_deleting_dependents)
        with pytest.raises(RuntimeError, match="abort native cascade"):
            await repos.users.delete(target.id)
    assert await snapshot() == before
    assert target_directory.exists()
    await repos.users.delete(target.id)
    assert await repos.users.get_one(target.id) is None
    assert await repos.users.get_one(survivor.id) is not None
    assert await repos.api_tokens.get_one(survivor_token.id) is not None
    assert not target_directory.exists()
    assert await LongLiveToken.filter(user_id=target.id).count() == 0
    assert await PasswordResetModel.filter(user_id=target.id).count() == 0
    assert await UserToRecipe.filter(user_id=target.id).count() == 0
    assert (await bridge.related_record("recipes", "id", recipe_id))["rating"] == 3
    owned_recipe = await bridge.related_record("recipes", "id", owned_recipe_id)
    assert owned_recipe is not None
    assert owned_recipe["user_id"] is None
    assert UUID(owned_recipe["group_id"]) == target.group_id
    for table in tables[5:]:
        assert await bridge.execute(f'SELECT * FROM "{table}"') == []


@pytest.mark.asyncio
async def test_native_user_token_replacement_preserves_ownership_and_atomicity(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    first, second = native_user_repositories
    user = await create_native_user(first, "token-owner")
    foreign_user = await create_native_user(second, "foreign-token-owner")
    kept = await first.api_tokens.create({"user_id": user.id, "name": "kept", "token": "kept-secret"})
    removed = await first.api_tokens.create({"user_id": user.id, "name": "removed", "token": "removed-secret"})
    foreign = await second.api_tokens.create({"user_id": foreign_user.id, "name": "foreign", "token": "foreign-secret"})
    updated = await first.users.patch(user.id, {"tokens": [{"id": kept.id, "name": "renamed"}]})
    assert [(token.id, token.name) for token in updated.tokens] == [(kept.id, "renamed")]
    assert (await LongLiveToken.get(id=kept.id)).token == "kept-secret"
    assert not await LongLiveToken.filter(id=removed.id).exists()
    assert (await LongLiveToken.get(id=foreign.id)).name == "foreign"

    before_user = await first.users.get_one(user.id)
    before_tokens = await LongLiveToken.all().order_by("id").values()
    with pytest.raises(ValueError):
        await first.users.patch(
            user.id,
            {
                "full_name": "rolled-back-name",
                "tokens": [
                    {"id": kept.id, "name": "rolled-back-token"},
                    {"id": foreign.id, "name": "stolen-token"},
                ],
            },
        )
    assert await first.users.get_one(user.id) == before_user
    assert await LongLiveToken.all().order_by("id").values() == before_tokens

    cleared = await first.users.patch(user.id, {"tokens": []})
    assert cleared.tokens == []
    assert not await LongLiveToken.filter(user_id=user.id).exists()
    assert (await LongLiveToken.get(id=foreign.id)).user_id == foreign_user.id
