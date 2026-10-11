import json
import shutil
import sqlite3
from collections.abc import AsyncGenerator, Generator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError

from mealie.core.config import get_app_settings
from mealie.core.settings import AppSettings
from mealie.core.settings.db_providers import SQLiteProvider
from mealie.db.init_db import ALEMBIC_DIR
from mealie.db.models.group.group import Group
from mealie.db.models.server.task import ServerTaskModel
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.services.backups_v2.alchemy_exporter import AlchemyExporter


@pytest.fixture(scope="module")
def migrated_server_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Exercise the production migration schema while legacy domains coexist."""
    provider = SQLiteProvider(data_dir=tmp_path_factory.mktemp("server_migrations"))
    settings = get_app_settings().model_copy(update={"DB_PROVIDER": provider})
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("mealie.core.config.get_app_settings", lambda: settings)
        command.upgrade(Config(str(ALEMBIC_DIR / "alembic.ini")), "head")
    return provider.db_path


@pytest.fixture
def server_settings(tmp_path: Path, migrated_server_database: Path) -> AppSettings:
    provider = SQLiteProvider(data_dir=tmp_path)
    shutil.copyfile(migrated_server_database, provider.db_path)
    return get_app_settings().model_copy(
        update={"DB_PROVIDER": provider, "TESTING": True, "SQLITE_MIGRATE_JOURNAL_WAL": False}
    )


@pytest.fixture
def server_engine(server_settings: AppSettings) -> Generator[Engine]:
    assert server_settings.DB_URL is not None
    engine = create_engine(server_settings.DB_URL)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection: sqlite3.Connection, _record: ConnectionPoolEntry) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        yield engine
    finally:
        engine.dispose()


@pytest_asyncio.fixture
async def server_connection(server_settings: AppSettings) -> AsyncGenerator[BaseDBAsyncClient]:
    async with database_context(get_tortoise_config(server_settings)) as context:
        yield context.db()


def create_group(engine: Engine) -> UUID:
    with Session(engine) as session:
        group = Group(name=f"server-{uuid4()}", session=session)
        session.add(group)
        session.commit()
        return UUID(str(group.id))


@pytest.mark.asyncio
async def test_server_model_is_registered_with_the_default_connection(server_settings: AppSettings) -> None:
    config = get_tortoise_config(server_settings)
    assert config["apps"] == {"models": {"models": ["mealie.db.models.server.task"], "default_connection": "default"}}
    config["apps"]["models"]["models"].append("unused.module")
    fresh_config = get_tortoise_config(server_settings)
    assert fresh_config["apps"]["models"]["models"] == ["mealie.db.models.server.task"]
    async with database_context(fresh_config) as context:
        assert context.get_model("models", "ServerTaskModel") is ServerTaskModel
        assert ServerTaskModel._meta.db is context.db()


@pytest.mark.asyncio
async def test_server_task_crud_preserves_legacy_storage(
    server_engine: Engine, server_connection: BaseDBAsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    group_id = create_group(server_engine)
    created = datetime(2026, 1, 1, tzinfo=UTC)
    updated = created + timedelta(days=1)
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: created)
    task = await ServerTaskModel.create(name="task" * 1000, status="pending" * 1000, group_id=group_id)

    assert isinstance(task.id, int)
    assert task.created_at == created
    assert task.updated_at == created
    assert task.completed_date is None
    assert task.log is None
    assert await ServerTaskModel.filter(group_id=str(group_id)).count() == 1
    assert await ServerTaskModel.filter(group_id=group_id.hex).count() == 1

    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: updated)
    task.status = "finished"
    task.completed_date = datetime(2026, 1, 2, 3, tzinfo=timezone(timedelta(hours=2)))
    task.log = "output\n" * 1000
    await task.save(update_fields=["status", "completed_date", "log", "update_at"])
    saved = await ServerTaskModel.get(id=task.id)

    assert saved.name == "task" * 1000
    assert saved.status == "finished"
    assert saved.log == "output\n" * 1000
    assert saved.group_id == group_id
    assert saved.created_at == created
    assert saved.update_at == updated
    assert saved.updated_at == updated
    assert saved.completed_date == datetime(2026, 1, 2, 1, tzinfo=UTC)

    rows = await server_connection.execute_query_dict('SELECT * FROM "server_tasks" WHERE "id" = ?', [task.id])
    assert rows[0]["group_id"] == group_id.hex
    assert datetime.fromisoformat(rows[0]["created_at"]) == created.replace(tzinfo=None)
    assert datetime.fromisoformat(rows[0]["update_at"]) == updated.replace(tzinfo=None)
    assert datetime.fromisoformat(rows[0]["completed_date"]) == datetime(2026, 1, 2, 1, tzinfo=UTC).replace(tzinfo=None)

    await saved.delete()
    assert not await ServerTaskModel.filter(id=task.id).exists()

    await server_connection.execute_query(
        'INSERT INTO "server_tasks" ("name", "status", "group_id") VALUES (?, ?, ?)',
        ["legacy", "pending", group_id.hex],
    )
    legacy = await ServerTaskModel.get(name="legacy")
    assert legacy.group_id == group_id
    assert legacy.created_at is None
    assert legacy.updated_at is None
    assert legacy.completed_date is None
    assert legacy.log is None


@pytest.mark.asyncio
async def test_server_task_rejects_unknown_group(server_connection: BaseDBAsyncClient) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        await ServerTaskModel.create(name="orphan", status="pending", group_id=uuid4())
    assert await ServerTaskModel.all().count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("rollback", [False, True])
async def test_group_deletion_cleans_tasks_in_the_same_transaction(
    server_engine: Engine, server_connection: BaseDBAsyncClient, rollback: bool
) -> None:
    group_id = create_group(server_engine)
    other_group_id = create_group(server_engine)
    task = await ServerTaskModel.create(name="owned", status="pending", group_id=group_id)
    other_task = await ServerTaskModel.create(name="other", status="pending", group_id=other_group_id)

    with pytest.raises(RuntimeError, match="abort group deletion") if rollback else nullcontext():
        with Session(server_engine) as session, session.begin():
            group = session.get(Group, group_id)
            assert group is not None
            session.delete(group)
            session.flush()
            assert session.execute(text("SELECT id FROM server_tasks")).scalars().all() == [other_task.id]
            if rollback:
                raise RuntimeError("abort group deletion")

    assert await ServerTaskModel.filter(id=task.id).exists() is rollback
    assert await ServerTaskModel.filter(id=other_task.id, group_id=other_group_id).exists()
    with Session(server_engine) as session:
        assert (session.get(Group, group_id) is not None) is rollback
        assert session.get(Group, other_group_id) is not None


@pytest.mark.asyncio
async def test_server_tasks_survive_the_legacy_backup_restore(
    server_settings: AppSettings, server_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    group_id = create_group(server_engine)
    completed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    config = get_tortoise_config(server_settings)
    async with database_context(config):
        task = await ServerTaskModel.create(
            name="completed", status="finished", log="restorable\noutput", completed_date=completed, group_id=group_id
        )
        pending = await ServerTaskModel.create(name="pending", status="pending", group_id=group_id)

    assert server_settings.DB_URL is not None
    exporter = AlchemyExporter(server_settings.DB_URL)
    try:
        backup = json.loads(json.dumps(exporter.dump()))
        assert len(backup["server_tasks"]) == 2
        exporter.drop_all()
        # The restore's migration environment and bootstrap must stay isolated
        # from the worker's shared application database.
        monkeypatch.setattr("mealie.core.config.get_app_settings", lambda: server_settings)
        monkeypatch.setattr("mealie.db.init_db.main", lambda: None)
        exporter.restore(backup)
    finally:
        exporter.engine.dispose()

    async with database_context(config):
        restored = await ServerTaskModel.get(id=task.id)
        assert restored.name == task.name
        assert restored.status == task.status
        assert restored.log == task.log
        assert restored.group_id == group_id
        assert restored.created_at == task.created_at
        assert restored.updated_at == task.updated_at
        assert restored.completed_date == completed
        restored_pending = await ServerTaskModel.get(id=pending.id)
        assert restored_pending.group_id == group_id
        assert restored_pending.completed_date is None
        assert restored_pending.log is None
