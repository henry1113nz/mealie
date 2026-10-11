import asyncio
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from tortoise.connection import get_connection
from tortoise.context import get_current_context
from tortoise.transactions import in_transaction

from mealie.core.config import get_app_settings
from mealie.core.settings.db_providers import SQLiteProvider
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context


@pytest.fixture
def database_config(tmp_path: Path) -> dict[str, Any]:
    settings = get_app_settings().model_copy(
        update={
            "DB_PROVIDER": SQLiteProvider(data_dir=tmp_path),
            "TESTING": False,
            "SQLITE_MIGRATE_JOURNAL_WAL": False,
        }
    )
    return get_tortoise_config(settings)


@pytest.mark.asyncio
async def test_context_closes_connections_without_creating_tables(database_config: dict[str, Any]) -> None:
    previous_context = get_current_context()
    async with database_context(database_config) as context:
        client = context.db()
        assert get_current_context() is context
        assert await client.execute_query_dict("SELECT name FROM sqlite_master WHERE type='table'") == []
    assert client._connection is None
    assert get_current_context() is previous_context


@pytest.mark.asyncio
async def test_context_closes_connections_after_error(database_config: dict[str, Any]) -> None:
    previous_context = get_current_context()
    with pytest.raises(RuntimeError, match="work failed"):
        async with database_context(database_config) as context:
            client = context.db()
            raise RuntimeError("work failed")
    assert client._connection is None
    assert get_current_context() is previous_context


@pytest.mark.asyncio
async def test_context_cleans_up_when_connection_fails(database_config: dict[str, Any], tmp_path: Path) -> None:
    database_config["connections"]["default"]["credentials"]["file_path"] = str(tmp_path / "missing" / "db.sqlite")
    previous_context = get_current_context()
    with pytest.raises(sqlite3.OperationalError, match="unable to open database"):
        async with database_context(database_config, global_fallback=True):
            pytest.fail("An unavailable database must fail during startup")
    assert get_current_context() is previous_context


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_mode", ["delete", "wal"])
async def test_disabled_wal_setting_preserves_existing_journal_mode(
    database_config: dict[str, Any], initial_mode: str
) -> None:
    db_path = database_config["connections"]["default"]["credentials"]["file_path"]
    with sqlite3.connect(db_path) as connection:
        connection.execute(f"PRAGMA journal_mode={initial_mode}")
    connection.close()

    async with database_context(database_config) as context:
        assert await context.db().execute_query_dict("PRAGMA journal_mode") == [{"journal_mode": initial_mode}]


@pytest.mark.asyncio
@pytest.mark.parametrize("wal", [False, True])
async def test_testing_pragmas_and_foreign_keys_are_applied(tmp_path: Path, wal: bool) -> None:
    settings = get_app_settings().model_copy(
        update={
            "DB_PROVIDER": SQLiteProvider(data_dir=tmp_path),
            "TESTING": True,
            "SQLITE_MIGRATE_JOURNAL_WAL": wal,
        }
    )
    async with database_context(get_tortoise_config(settings)) as context:
        assert await context.db().execute_query_dict("PRAGMA journal_mode") == [
            {"journal_mode": "wal" if wal else "memory"}
        ]
        assert await context.db().execute_query_dict("PRAGMA synchronous") == [{"synchronous": 0}]
        assert await context.db().execute_query_dict("PRAGMA foreign_keys") == [{"foreign_keys": 1}]


@pytest.mark.asyncio
async def test_transactions_commit_and_rollback(database_config: dict[str, Any]) -> None:
    async with database_context(database_config) as context:
        await context.db().execute_script("CREATE TABLE foundation_transaction (value INTEGER NOT NULL)")
        async with in_transaction("default") as transaction:
            await transaction.execute_query("INSERT INTO foundation_transaction VALUES (?)", [1])
        with pytest.raises(RuntimeError, match="rollback"):
            async with in_transaction("default") as transaction:
                await transaction.execute_query("INSERT INTO foundation_transaction VALUES (?)", [2])
                raise RuntimeError("rollback")
        assert await context.db().execute_query_dict("SELECT value FROM foundation_transaction") == [{"value": 1}]


@pytest.mark.asyncio
async def test_lifespan_context_is_available_to_sibling_request_tasks(database_config: dict[str, Any]) -> None:
    ready = asyncio.Event()

    async def request() -> list[dict[str, Any]]:
        await ready.wait()
        return await get_connection("default").execute_query_dict("SELECT 1 AS value")

    # Start before entering the context, like ASGI's sibling request/lifespan tasks.
    async with asyncio.TaskGroup() as tasks:
        task = tasks.create_task(request())
        async with database_context(database_config, global_fallback=True):
            ready.set()
            assert await task == [{"value": 1}]
    assert get_current_context() is None


@pytest.mark.asyncio
async def test_app_closes_database_when_scheduler_startup_fails(
    database_config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import mealie.app as application
    import mealie.db.init_db as legacy_init
    import mealie.db.tortoise_setup as setup

    clients = []

    async def fail_scheduler() -> None:
        clients.append(get_connection("default"))
        raise RuntimeError("scheduler startup failed")

    monkeypatch.setattr(legacy_init, "prepare_database", AsyncMock(return_value=False))
    monkeypatch.setattr(legacy_init, "initialize_data", AsyncMock())
    monkeypatch.setattr(setup, "get_tortoise_config", lambda: database_config)
    monkeypatch.setattr(application, "start_scheduler", fail_scheduler)
    with pytest.raises(RuntimeError, match="scheduler startup failed"):
        async with application.lifespan_fn(application.app):
            pytest.fail("A failed scheduler must fail application startup")
    assert len(clients) == 1
    assert clients[0]._connection is None
    assert get_current_context() is None
