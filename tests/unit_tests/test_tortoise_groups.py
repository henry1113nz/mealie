"""Exercise converted groups against the production schema and active async transaction."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from freezegun import freeze_time
from sqlalchemy import Engine
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from mealie.core.settings import AppSettings
from mealie.db.models._tortoise_base import TortoiseBase
from mealie.db.models.group import (
    AIProvider,
    AIProviderHeaders,
    AIProviderParams,
    AIProviderSettings,
    Group,
    GroupDataExportsModel,
    GroupPreferencesModel,
    ReportEntryModel,
    ReportModel,
)
from mealie.db.models.server.task import ServerTaskModel
from mealie.db.models.users.users import User
from mealie.db.tortoise_config import TORTOISE_MODEL_MODULES, get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.repos import _users_coexistence as bridge
from mealie.repos.all_repositories import AllRepositories
from mealie.schema.group.ai_providers import AIProviderCreate, AIProviderUpdate
from mealie.schema.recipe.recipe import Recipe
from mealie.schema.response.pagination import OrderDirection, PaginationQuery
from mealie.services.scheduler.tasks.purge_group_exports import purge_group_data_exports
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_engine as server_engine
from tests.unit_tests.test_tortoise_server import server_settings as server_settings
from tests.unit_tests.test_tortoise_users import create_native_user
from tests.unit_tests.test_tortoise_users import native_user_repositories as native_user_repositories


@pytest.mark.asyncio
async def test_group_registry_and_native_cross_domain_relations(
    server_settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Preserve C4 registry expectations in isolated setup; C5 covers the expanded registry.
    monkeypatch.setattr("mealie.db.tortoise_config.TORTOISE_MODEL_MODULES", TORTOISE_MODEL_MODULES[:9])
    config = get_tortoise_config(server_settings)
    assert config["apps"]["models"]["models"] == [
        "mealie.db.models.server.task",
        "mealie.db.models.users.users",
        "mealie.db.models.users.password_reset",
        "mealie.db.models.users.user_to_recipe",
        "mealie.db.models.group.group",
        "mealie.db.models.group.preferences",
        "mealie.db.models.group.ai_providers",
        "mealie.db.models.group.exports",
        "mealie.db.models.group.report",
    ]
    config["apps"]["models"]["models"].append("unused.module")
    assert "unused.module" not in get_tortoise_config(server_settings)["apps"]["models"]["models"]
    config["apps"]["models"]["models"] = list(TORTOISE_MODEL_MODULES)
    async with database_context(config) as context:
        for model in (
            Group,
            GroupPreferencesModel,
            GroupDataExportsModel,
            ReportModel,
            ReportEntryModel,
            AIProviderSettings,
            AIProvider,
            AIProviderHeaders,
            AIProviderParams,
        ):
            assert issubclass(model, TortoiseBase)
            assert context.get_model("models", model.__name__) is model
            assert model._meta.db is context.db()
        group = await Group.create(name="Relations")
        task = await ServerTaskModel.create(group_id=group.id, name="task", status="pending")
        user = await User.create(group_id=group.id, username="native", email="native@example.test", password="stored")
        assert (await task.group).id == group.id
        assert (await user.group).id == group.id
        assert [entry.id for entry in await group.server_tasks] == [task.id]
        assert [entry.id for entry in await group.users] == [user.id]


@pytest.mark.asyncio
async def test_group_storage_defaults_nullability_constraints_and_utc(
    server_settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = datetime(2026, 4, 5, tzinfo=UTC)
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: created)
    async with database_context(get_tortoise_config(server_settings)) as context:
        group = await Group.create(name="group" * 1000)
        preferences = await GroupPreferencesModel.create(group_id=group.id)
        assert group.slug is None
        assert group.created_at == created
        assert preferences.private_group is True
        assert preferences.show_announcements is True
        assert preferences.first_day_of_week == 0
        assert preferences.recipe_disable_amount is True
        preferences.private_group = None
        await preferences.save()
        assert (await GroupPreferencesModel.get(id=preferences.id)).private_group is None
        report = await ReportModel.create(
            group_id=group.id,
            name="report" * 1000,
            category="migration",
            status="in-progress",
            timestamp=datetime(2026, 4, 5, 5, tzinfo=timezone(timedelta(hours=5))),
        )
        entry = await ReportEntryModel.create(report_id=report.id, message=None, exception=None)
        assert entry.success is False
        assert entry.message is None
        assert entry.exception is None
        assert report.timestamp == created
        export = await GroupDataExportsModel.create(
            group_id=None,
            name="orphan export",
            filename="archive.zip",
            path="/tmp/archive.zip",
            size="12",
            expires="later",
        )
        assert export.group_id is None
        settings = await AIProviderSettings.create(group_id=group.id)
        provider = await AIProvider.create(
            settings_id=settings.id, name="provider" * 1000, api_key="secret", model="model"
        )
        header = await AIProviderHeaders.create(provider_id=provider.id, key_name=None, value="value" * 1000)
        assert provider.timeout == 300
        assert provider.base_url is None
        assert header.key_name is None
        assert header.created_at == created
        rows = await context.db().execute_query_dict("SELECT * FROM group_reports WHERE id = ?", [report.id.hex])
        assert rows[0]["group_id"] == group.id.hex
        assert datetime.fromisoformat(rows[0]["timestamp"]) == created.replace(tzinfo=None)
        assert datetime.fromisoformat(rows[0]["created_at"]) == created.replace(tzinfo=None)
        with pytest.raises(IntegrityError):
            await Group.create(name=group.name)
        with pytest.raises(IntegrityError):
            await AIProviderSettings.create(group_id=group.id)
        with pytest.raises(IntegrityError):
            await AIProvider.create(settings_id=settings.id, name=provider.name, api_key="secret", model="model")
        with pytest.raises(IntegrityError):
            await GroupPreferencesModel.create(group_id=uuid4())
        with pytest.raises(IntegrityError):
            await ReportEntryModel.create(report_id=uuid4())
        updated = created + timedelta(days=1)
        monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: updated)
        group.name = "renamed"
        await group.save(update_fields=["name", "update_at"])
        assert (await Group.get(id=group.id)).updated_at == updated


@pytest.mark.asyncio
async def test_group_repository_hydration_slugs_filters_and_preference_scope(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    group = await repos.groups.get_one(repos.group_id)
    preference = await repos.group_preferences.create({"group_id": group.id, "private_group": False})
    hydrated = await repos.groups.get_by_slug_or_id(group.slug)
    assert hydrated.preferences == preference
    assert hydrated.households[0].id == (await repos.households.get_all())[0].id
    assert await other.group_preferences.get_one(group.id) is None
    page = await repos.groups.page_all(
        PaginationQuery(query_filter=f"id={group.id}", order_by="name", order_direction=OrderDirection.asc)
    )
    assert [item.id for item in page.items] == [group.id]
    duplicates = await repos.groups.create_many([{"name": "Same Name"}, {"name": "Same Name"}])
    assert [item.name for item in duplicates] == ["Same Name", "Same Name (1)"]
    assert [item.slug for item in duplicates] == ["same-name", "same-name-1"]
    renamed = await repos.groups.update(duplicates[0].id, {"name": "Different Name"})
    assert renamed.slug == "different-name"
    with pytest.raises(RuntimeError, match="rollback"):
        async with in_transaction("default"):
            await repos.group_preferences.patch(group.id, {"private_group": True})
            raise RuntimeError("rollback")
    assert (await repos.group_preferences.get_one(group.id)).private_group is False


@pytest.mark.asyncio
async def test_reports_are_scoped_and_delete_entries_transactionally(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    report = await repos.group_reports.create(
        {"group_id": repos.group_id, "name": "Import", "category": "migration", "status": "in-progress"}
    )
    entry = await repos.group_report_entries.create(
        {"report_id": report.id, "success": True, "message": "Imported", "exception": ""}
    )
    assert (await repos.group_reports.get_one(report.id)).entries == [entry]
    assert await other.group_reports.get_one(report.id) is None
    assert await other.group_report_entries.get_one(entry.id) is None
    assert (await other.group_report_entries.page_all(PaginationQuery(per_page=-1))).items == []
    with pytest.raises(RuntimeError, match="rollback"):
        async with in_transaction("default"):
            await repos.group_reports.delete(report.id)
            assert not await ReportEntryModel.filter(id=entry.id).exists()
            raise RuntimeError("rollback")
    assert await ReportEntryModel.filter(id=entry.id).exists()
    await repos.group_reports.delete(report.id)
    assert not await ReportModel.filter(id=report.id).exists()
    assert not await ReportEntryModel.filter(id=entry.id).exists()


@pytest.mark.asyncio
async def test_ai_provider_children_keys_selection_and_tenant_ownership(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, other = native_user_repositories
    for repository in (repos, other):
        await repository.group_ai_provider_settings.create({"group_id": repository.group_id})
    provider = await repos.group_ai_providers.create(
        AIProviderCreate(
            name="Native provider",
            api_key="secret",
            model="model",
            request_headers={"X-Token": "token"},
            request_params={"mode": "strict"},
        )
    )
    assert provider.api_key == "secret"
    assert "api_key" not in provider.model_dump()
    assert provider.request_headers == {"X-Token": "token"}
    assert provider.request_params == {"mode": "strict"}
    assert await other.group_ai_providers.get_one(provider.id) is None
    settings = await repos.group_ai_provider_settings.update(
        repos.group_id,
        {"default_provider_id": provider.id, "audio_provider_id": provider.id, "image_provider_id": provider.id},
    )
    assert settings.ai_enabled and settings.audio_provider_enabled and settings.image_provider_enabled
    with pytest.raises(ValueError, match="Provider does not belong"):
        await other.group_ai_provider_settings.update(other.group_id, {"default_provider_id": provider.id})
    changed = await repos.group_ai_providers.update(
        provider.id,
        AIProviderUpdate(
            name="Native provider", model="changed", request_headers={"Other": "value"}, request_params={}
        ),
    )
    assert changed.api_key == "secret"
    assert changed.request_headers == {"Other": "value"}
    assert changed.request_params == {}
    assert await AIProviderHeaders.filter(provider_id=provider.id).count() == 1
    assert await AIProviderParams.filter(provider_id=provider.id).count() == 0
    await repos.group_ai_providers.delete(provider.id)
    settings = await repos.group_ai_provider_settings.get_one(repos.group_id)
    assert settings.default_provider_id is None
    assert settings.audio_provider_id is None
    assert settings.image_provider_id is None
    assert settings.providers == []
    assert await AIProviderHeaders.filter(provider_id=provider.id).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("rollback", [False, True])
async def test_group_delete_cleans_owned_domains_and_preserves_other_group(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
    server_engine: Engine,
    rollback: bool,
) -> None:
    repos, other = native_user_repositories
    group_id = repos.group_id
    await repos.group_preferences.create({"group_id": group_id})
    await repos.group_ai_provider_settings.create({"group_id": group_id})
    provider = await repos.group_ai_providers.create(
        AIProviderCreate(name="Delete", api_key="secret", model="model", request_headers={"X": "Y"})
    )
    await repos.group_ai_provider_settings.update(group_id, {"default_provider_id": provider.id})
    report = await repos.group_reports.create(
        {"group_id": group_id, "name": "Delete", "category": "migration", "status": "success"}
    )
    await repos.group_report_entries.create(
        {"report_id": report.id, "message": "entry", "exception": "", "success": True}
    )
    task = await ServerTaskModel.create(group_id=group_id, name="Delete", status="pending")
    other_task = await ServerTaskModel.create(group_id=other.group_id, name="Keep", status="pending")
    # Populate household and recipe dependents through the still-legacy repositories.
    owner = await create_native_user(repos, "former-owner")
    recipe = repos.recipes.create(
        Recipe.model_validate(
            {
                "name": "Delete recipe",
                "group_id": group_id,
                "user_id": owner.id,
                "recipe_ingredient": [{"note": "ingredient"}],
                "recipe_instructions": [{"text": "Step"}],
                "extras": {"key": "value"},
            }
        )
    )
    await repos.users.delete(owner.id)
    try:
        async with in_transaction("default"):
            await repos.groups.delete(group_id)
            assert not await Group.filter(id=group_id).exists()
            assert not await ServerTaskModel.filter(id=task.id).exists()
            assert await bridge.related_record("recipes", "id", recipe.id) is None
            assert await bridge.execute("SELECT id FROM households WHERE group_id = ?", [group_id]) == []
            if rollback:
                raise RuntimeError("rollback")
    except RuntimeError:
        if not rollback:
            raise
    assert await Group.filter(id=group_id).exists() is rollback
    assert await ServerTaskModel.filter(id=task.id).exists() is rollback
    assert await ReportModel.filter(id=report.id).exists() is rollback
    assert await AIProvider.filter(id=provider.id).exists() is rollback
    assert (await bridge.related_record("recipes", "id", recipe.id) is not None) is rollback
    assert await ServerTaskModel.filter(id=other_task.id).exists()
    assert await Group.filter(id=other.group_id).exists()


@pytest.mark.asyncio
async def test_group_with_users_cannot_be_deleted(
    native_user_repositories: tuple[AllRepositories, AllRepositories],
) -> None:
    repos, _ = native_user_repositories
    user = await create_native_user(repos, "retained")
    with pytest.raises(IntegrityError):
        await repos.groups.delete(repos.group_id)
    assert await User.filter(id=user.id, group_id=repos.group_id).exists()
    assert await Group.filter(id=repos.group_id).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("expires", ["2026-04-05T11:00:00", "2026-04-05 11:00:00", "2026-04-05T16:00:00+05:00"])
async def test_export_purge_compares_text_expiry_as_utc(
    native_user_repositories: tuple[AllRepositories, AllRepositories], tmp_path: Path, expires: str
) -> None:
    repos, _ = native_user_repositories
    expired_path = tmp_path / "expired.zip"
    retained_path = tmp_path / "retained.zip"
    expired_path.write_bytes(b"expired")
    retained_path.write_bytes(b"retained")
    for path, expiry in ((expired_path, expires), (retained_path, "2026-04-05T13:00:00+00:00")):
        await GroupDataExportsModel.create(
            group_id=repos.group_id, name=path.stem, filename=path.name, path=str(path), size="7", expires=expiry
        )
    with freeze_time("2026-04-05T12:00:00+00:00", real_asyncio=True):
        await purge_group_data_exports(max_minutes_old=0)
    assert not expired_path.exists()
    assert retained_path.exists()
    assert await GroupDataExportsModel.filter(name="expired").count() == 0
    assert await GroupDataExportsModel.filter(name="retained").count() == 1
