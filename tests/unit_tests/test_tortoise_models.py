from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from tortoise import Model, Tortoise, fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.connection import get_connection
from tortoise.context import TortoiseContext

from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._tortoise_base import TortoiseBase, UTCDateTimeField, UUIDField


class FoundationRecord(TortoiseBase):
    identifier = UUIDField(unique=True)
    name = fields.CharField(max_length=100)
    occurred_at = UTCDateTimeField(null=True)

    class Meta:
        table = "foundation_records"


@pytest_asyncio.fixture
async def foundation_connection() -> AsyncGenerator[BaseDBAsyncClient]:
    async with TortoiseContext():
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": [__name__]}, use_tz=True, timezone="UTC")
        await Tortoise.generate_schemas()
        yield get_connection("default")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Gluten-Free Bread", "gluten free bread"),
        ("Mac & Cheese", "mac   cheese"),
        ("Chicken/Rice Bowl", "chicken rice bowl"),
        ("Rátàtôuile", "ratatouile"),
        ('Mom\'s "Pasta"', 'mom\'s "pasta"'),
        ("  " + "É" * 300, "e" * 255),
    ],
)
def test_normalization_preserves_search_and_legacy_storage(value: str, expected: str) -> None:
    assert TortoiseBase.normalize(value) == expected
    assert TortoiseBase.normalize(value) == SqlAlchemyBase.normalize(value)


@pytest.mark.asyncio
async def test_automatic_timestamps_preserve_columns_and_alias(
    foundation_connection: BaseDBAsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    updated = created + timedelta(days=1)
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: created)
    record = await FoundationRecord.create(identifier=uuid4(), name="first")

    assert isinstance(record.id, int)
    assert record.created_at == created
    assert record.updated_at == created
    monkeypatch.setattr("tortoise.fields.data.timezone.now", lambda: updated)
    record.name = "second"
    await record.save()

    saved = await FoundationRecord.get(id=record.id)
    assert saved.created_at == created
    assert saved.update_at == updated
    assert saved.updated_at == updated
    saved.updated_at = created
    assert saved.update_at == created

    columns = await foundation_connection.execute_query_dict('PRAGMA table_info("foundation_records")')
    assert {column["name"] for column in columns} == {
        "id",
        "created_at",
        "update_at",
        "identifier",
        "name",
        "occurred_at",
    }
    rows = await foundation_connection.execute_query_dict('SELECT "created_at", "update_at" FROM "foundation_records"')
    assert datetime.fromisoformat(rows[0]["created_at"]).tzinfo is None
    assert datetime.fromisoformat(rows[0]["update_at"]).tzinfo is None


@pytest.mark.asyncio
async def test_uuid_and_datetime_interoperate_with_legacy_sqlite_storage(
    foundation_connection: BaseDBAsyncClient,
) -> None:
    identifier = uuid4()
    offset_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=2)))
    expected = offset_time.astimezone(UTC)
    record = await FoundationRecord.create(identifier=identifier, name="async", occurred_at=offset_time)

    rows = await foundation_connection.execute_query_dict(
        'SELECT "identifier", "occurred_at" FROM "foundation_records" WHERE "id" = ?', [record.id]
    )
    assert rows[0]["identifier"] == identifier.hex
    assert datetime.fromisoformat(rows[0]["occurred_at"]) == expected.replace(tzinfo=None)
    assert await FoundationRecord.filter(identifier=identifier.hex).count() == 1
    assert await FoundationRecord.filter(identifier=str(identifier)).count() == 1

    legacy_identifier = uuid4()
    await foundation_connection.execute_query(
        'INSERT INTO "foundation_records" ("identifier", "name", "occurred_at") VALUES (?, ?, ?)',
        [legacy_identifier.hex, "legacy", "2026-01-02 01:04:05.000000"],
    )
    legacy_record = await FoundationRecord.get(identifier=legacy_identifier)
    assert legacy_record.identifier == legacy_identifier
    assert legacy_record.occurred_at == expected
    assert legacy_record.created_at is None
    assert legacy_record.updated_at is None


@pytest.mark.parametrize("dialect, expected_type", [("sqlite", "CHAR(32)"), ("postgres", "UUID")])
def test_uuid_field_preserves_backend_representation(dialect: str, expected_type: str) -> None:
    field = UUIDField(null=True)
    model = cast(
        Model, SimpleNamespace(_meta=SimpleNamespace(db=SimpleNamespace(capabilities=SimpleNamespace(dialect=dialect))))
    )
    identifier = UUID("193984d6-e8c2-429a-bb6c-19d4a6b728fc")
    expected_value = identifier.hex if dialect == "sqlite" else str(identifier)

    assert field.get_for_dialect(dialect, "SQL_TYPE") == expected_type
    assert field.to_db_value(identifier, model) == expected_value
    assert field.to_python_value(expected_value) == identifier
    assert field.to_db_value(None, model) is None
    assert field.to_python_value(None) is None


def test_postgres_timestamp_type_preserves_naive_storage() -> None:
    field = UTCDateTimeField(null=True)
    timestamp = datetime(2026, 1, 2, 3, tzinfo=timezone(timedelta(hours=2)))
    assert field.get_for_dialect("postgres", "SQL_TYPE") == "TIMESTAMP"
    assert field.to_db_value(timestamp, FoundationRecord) == datetime(2026, 1, 2, 1, tzinfo=UTC).replace(tzinfo=None)
    assert field.to_python_value(None) is None
