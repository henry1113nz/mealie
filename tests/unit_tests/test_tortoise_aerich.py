from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from aerich.models import Aerich
from tortoise import BaseDBAsyncClient
from tortoise.context import TortoiseContext
from tortoise.exceptions import IntegrityError, OperationalError
from tortoise.fields.relational import ManyToManyFieldInstance
from tortoise.transactions import in_transaction

from mealie.db.init_db import MIGRATIONS_DIR, prepare_database
from mealie.db.models.group.ai_providers import AIProvider, AIProviderSettings
from mealie.db.models.group.group import Group
from mealie.db.models.recipe.ingredient import IngredientFoodModel, IngredientFoodSubstitutionModel
from mealie.db.schema_generator import POSTGRES_TEXT_INDEXES
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context


@pytest.fixture
def migration_config(tmp_path: Path) -> dict[str, Any]:
    config = get_tortoise_config()
    config["connections"]["default"] = {
        "engine": "mealie.db.tortoise_sqlite",
        "credentials": {"file_path": str(tmp_path / "aerich.db")},
    }
    return config


@pytest_asyncio.fixture
async def migration_connection(migration_config: dict[str, Any]) -> AsyncIterator[BaseDBAsyncClient]:
    async with database_context(migration_config) as context:
        await prepare_database()
        yield context.db()


@pytest.mark.asyncio
async def test_aerich_initial_migration_is_idempotent(migration_connection: BaseDBAsyncClient) -> None:
    group = await Group.create(name="Migration test", slug="migration-test")
    assert await prepare_database() is False
    assert await Group.get(id=group.id) == group
    assert await Aerich.filter(app="models").values_list("version", flat=True) == ["0_20261011000000_init.py"]
    assert await migration_connection.execute_query_dict("PRAGMA foreign_key_check") == []
    tables = await migration_connection.execute_query_dict("SELECT name FROM sqlite_master WHERE type='table'")
    assert len(tables) == 70
    assert "alembic_version" not in {table["name"] for table in tables}


@pytest.mark.asyncio
async def test_aerich_preserves_cycles_checks_and_join_indexes(migration_connection: BaseDBAsyncClient) -> None:
    group = await Group.create(name="Constraints", slug="constraints")
    settings = await AIProviderSettings.create(group_id=group.id)
    provider = await AIProvider.create(settings_id=settings.id, name="Test", api_key="test", model="test")
    settings.default_provider_id = provider.id
    await settings.save(update_fields=["default_provider_id"])
    with pytest.raises(IntegrityError):
        await AIProviderSettings.filter(id=settings.id).update(audio_provider_id=uuid4())
    with pytest.raises(IntegrityError):
        await provider.delete()
    food = await IngredientFoodModel.create(group_id=group.id, name="Food")
    with pytest.raises(IntegrityError):
        await IngredientFoodSubstitutionModel.create(food_id=food.id, substitute_food_id=food.id)
    with pytest.raises(IntegrityError):
        await IngredientFoodSubstitutionModel.create(food_id=food.id)
    from tortoise.context import get_current_context

    join_tables = 0
    for model in get_current_context().apps["models"].values():
        for field_name in model._meta.m2m_fields:
            field = model._meta.fields_map[field_name]
            if not isinstance(field, ManyToManyFieldInstance) or field._generated:
                continue
            join_tables += 1
            columns = await migration_connection.execute_query_dict(f'PRAGMA table_info("{field.through}")')
            assert all(not column["notnull"] for column in columns)
            indexes = await migration_connection.execute_query_dict(f'PRAGMA index_list("{field.through}")')
            indexed_columns = {
                tuple(
                    row["name"]
                    for row in await migration_connection.execute_query_dict(f'PRAGMA index_info("{index["name"]}")')
                )
                for index in indexes
            }
            assert (field.backward_key,) in indexed_columns
            assert (field.forward_key,) in indexed_columns
    assert join_tables == 12


@pytest.mark.asyncio
async def test_aerich_rejects_old_database_without_mutation(migration_config: dict[str, Any]) -> None:
    async with database_context(migration_config) as context:
        connection = context.db()
        await connection.execute_script(
            "CREATE TABLE alembic_version (version_num TEXT); INSERT INTO alembic_version VALUES ('old');"
        )
        with pytest.raises(RuntimeError, match="old Alembic schema"):
            await prepare_database()
        assert await connection.execute_query_dict("SELECT * FROM alembic_version") == [{"version_num": "old"}]
        assert await connection.execute_query_dict("SELECT name FROM sqlite_master WHERE type='table'") == [
            {"name": "alembic_version"}
        ]


@pytest.mark.asyncio
async def test_sqlite_migration_scripts_rollback_with_their_transaction(
    migration_connection: BaseDBAsyncClient,
) -> None:
    with pytest.raises(OperationalError):
        async with in_transaction("default") as connection:
            await connection.execute_script(
                "CREATE TABLE failed_migration (message TEXT);"
                "INSERT INTO failed_migration VALUES ('value; with semicolon');"
                "INSERT INTO missing_table VALUES (1);"
            )
    assert (
        await migration_connection.execute_query_dict("SELECT name FROM sqlite_master WHERE name='failed_migration'")
        == []
    )
    assert await Aerich.filter(app="models").count() == 1


@pytest.mark.asyncio
async def test_postgres_initial_ddl_retains_cycles_checks_and_search_indexes(migration_config: dict[str, Any]) -> None:
    migration_config["connections"]["default"] = {
        "engine": "mealie.db.tortoise_postgres",
        "credentials": {"host": "localhost", "port": 5432, "user": "test", "password": "test", "database": "test"},
    }
    async with TortoiseContext() as context:
        await context.init(config=migration_config)
        connection = context.db()
        generated = connection.schema_generator(connection).get_create_schema_sql(safe=False)
        snapshot = (MIGRATIONS_DIR / "models/0_20261011000000_init.postgres.sql").read_text()
        for sql in (generated, snapshot):
            assert "CREATE EXTENSION IF NOT EXISTS pg_trgm;" in sql
            assert sql.count(" CHECK (") == 3
            assert 'FOREIGN KEY ("owned_recipes_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT' in sql
            assert 'FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT' in sql
            assert 'FOREIGN KEY ("settings_id") REFERENCES "ai_provider_settings" ("id") ON DELETE RESTRICT' in sql
            for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
                assert f'FOREIGN KEY ("{field}") REFERENCES "ai_providers" ("id") ON DELETE RESTRICT' in sql
            for table, column in POSTGRES_TEXT_INDEXES:
                assert f'ON "{table}" USING gin ("{column}" gin_trgm_ops)' in sql
            assert sql.rfind("CREATE TABLE", 0, sql.index("ALTER TABLE")) >= 0
            assert "DISABLE TRIGGER" not in sql
            assert "FOREIGN_KEY_CHECKS" not in sql
