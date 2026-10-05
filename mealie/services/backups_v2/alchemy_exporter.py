"""Portable database backups using the active Tortoise connection.

The public exporter name and archive metadata are retained for compatibility with
existing backup consumers. Database creation and versioning are managed by Aerich.
"""

import datetime
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import import_module
from logging import Logger
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from tortoise import Tortoise
from tortoise.backends.base.client import BaseDBAsyncClient

from mealie.db.db_setup import native_connection_config
from mealie.services._base_service import BaseService

# Archive format metadata, not a live migration revision.
BACKUP_FORMAT_REVISION = "27621d27c7e1"


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


class ForeignKeyDisabler:
    def __init__(self, connection: BaseDBAsyncClient, dialect_name: str, *, logger: Logger | None = None) -> None:
        self.connection = connection
        self.is_postgres = dialect_name in {"postgres", "postgresql"}
        self.logger = logger
        self._initial_fk_state: str | int | None = None

    async def __aenter__(self) -> None:
        if self.is_postgres:
            # The caller supplies an active transaction so a pool release cannot
            # reset this setting before imports finish. LOCAL resets on rollback too.
            await self.connection.execute_script("SET LOCAL session_replication_role = 'replica';")
            return
        rows = await self.connection.execute_query_dict("PRAGMA foreign_keys")
        self._initial_fk_state = next(iter(rows[0].values())) if rows else None
        await self.connection.execute_script("PRAGMA foreign_keys = OFF;")

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self.is_postgres:
            state = "ON" if self._initial_fk_state else "OFF"
            await self.connection.execute_script(f"PRAGMA foreign_keys = {state};")


class AlchemyExporter(BaseService):
    look_for_datetime = {
        "created_at",
        "update_at",
        "updated_at",
        "date_updated",
        "timestamp",
        "expires_at",
        "locked_at",
        "last_made",
        "completed_date",
        "tokens_valid_after",
        "expires",
    }
    look_for_date = {"date_added", "date"}
    look_for_time = {"scheduled_time"}

    class DateTimeParser(BaseModel):
        date: datetime.date | None = None
        dt: datetime.datetime | None = None
        time: datetime.time | None = None

    def __init__(self, connection_str: str) -> None:
        super().__init__()
        self.connection_str = connection_str

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[BaseDBAsyncClient]:
        # A separate native connection keeps backup transactions and FK settings
        # isolated from HTTP requests, including SQLite's connection-wide pragmas.
        config = native_connection_config(self.connection_str)
        backend = import_module(config["engine"])
        connection = backend.client_class(connection_name="backup", **config["credentials"])
        try:
            await connection.create_connection(with_db=True)
            yield connection
        finally:
            await connection.close()

    @staticmethod
    def is_uuid(value: Any) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except ValueError, TypeError, AttributeError:
            return False

    def convert_types(self, data: Any) -> Any:
        if isinstance(data, list):
            return [self.convert_types(item) for item in data]
        if not isinstance(data, dict):
            return data
        converted = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                converted[key] = self.convert_types(value)
            elif isinstance(value, str) and key in self.look_for_datetime:
                converted[key] = self.DateTimeParser(dt=value).dt
            elif isinstance(value, str) and key in self.look_for_date:
                converted[key] = self.DateTimeParser(date=value).date
            elif isinstance(value, str) and key in self.look_for_time:
                converted[key] = self.DateTimeParser(time=value).time
            else:
                converted[key] = value
        return converted

    @staticmethod
    async def _tables(connection: BaseDBAsyncClient) -> list[str]:
        if connection.capabilities.dialect == "sqlite":
            rows = await connection.execute_query_dict(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [row["name"] for row in rows]
        rows = await connection.execute_query_dict(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() ORDER BY tablename"
        )
        return [row["tablename"] for row in rows]

    async def dump_schema(self) -> dict[str, list[dict[str, Any]]]:
        async with self._connection() as connection:
            tables = await self._tables(connection)
        return {**{name: [] for name in tables}, "alembic_version": [{"version_num": BACKUP_FORMAT_REVISION}]}

    async def dump(self) -> dict[str, list[dict[str, Any]]]:
        async with self._connection() as connection:
            async with connection._in_transaction() as transaction:
                if connection.capabilities.dialect != "sqlite":
                    await transaction.execute_script("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;")
                result = {
                    table: await transaction.execute_query_dict(f"SELECT * FROM {_quote(table)}")
                    for table in await self._tables(transaction)
                }
        result["alembic_version"] = [{"version_num": BACKUP_FORMAT_REVISION}]
        return jsonable_encoder(result)

    @staticmethod
    async def _column_types(connection: BaseDBAsyncClient, table: str) -> dict[str, str]:
        if connection.capabilities.dialect == "sqlite":
            rows = await connection.execute_query_dict(f"PRAGMA table_info({_quote(table)})")
            return {row["name"]: row["type"].lower() for row in rows}
        rows = await connection.execute_query_dict(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = $1",
            [table],
        )
        return {row["column_name"]: row["data_type"] for row in rows}

    @staticmethod
    def _database_value(value: Any, column_type: str, postgres: bool) -> Any:
        if value is None:
            return None
        if "json" in column_type:
            return json.dumps(value) if not isinstance(value, str) else value
        if postgres:
            if column_type == "uuid":
                return uuid.UUID(str(value))
            if "timestamp" in column_type and isinstance(value, str):
                return datetime.datetime.fromisoformat(value)
            if column_type == "date" and isinstance(value, str):
                return datetime.date.fromisoformat(value)
            if column_type.startswith("time") and isinstance(value, str):
                return datetime.time.fromisoformat(value)
            if column_type == "boolean":
                return bool(value)
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                return value.isoformat()
            if isinstance(value, (dict, list)):
                return json.dumps(value)
        return value

    async def restore(self, db_dump: dict[str, list[dict[str, Any]]]) -> None:
        if not db_dump.get("aerich"):
            from .legacy_import import prepare_legacy_backup

            db_dump = prepare_legacy_backup(db_dump)
        await Tortoise.generate_schemas(safe=True)
        async with self._connection() as connection:
            tables = [table for table in await self._tables(connection) if table != "aerich"]
            postgres = connection.capabilities.dialect != "sqlite"
            if postgres:
                async with connection._in_transaction() as transaction:
                    async with ForeignKeyDisabler(transaction, connection.capabilities.dialect, logger=self.logger):
                        await self._replace_rows(transaction, tables, db_dump, postgres=True)
            else:
                # SQLite only changes foreign key enforcement outside a transaction.
                async with ForeignKeyDisabler(connection, connection.capabilities.dialect, logger=self.logger):
                    async with connection._in_transaction() as transaction:
                        await self._replace_rows(transaction, tables, db_dump, postgres=False)

    async def _replace_rows(
        self,
        transaction: BaseDBAsyncClient,
        tables: list[str],
        db_dump: dict[str, list[dict[str, Any]]],
        *,
        postgres: bool,
    ) -> None:
        for table in tables:
            await transaction.execute_query(f"DELETE FROM {_quote(table)}")
        for table in tables:
            rows = db_dump.get(table, [])
            if not rows:
                continue
            types = await self._column_types(transaction, table)
            columns = [column for column in types if any(column in row for row in rows)]
            placeholders = [f"${i + 1}" if postgres else "?" for i in range(len(columns))]
            statement = (
                f"INSERT INTO {_quote(table)} ({', '.join(map(_quote, columns))}) VALUES ({', '.join(placeholders)})"
            )
            values = [
                [self._database_value(row.get(column), types[column], postgres) for column in columns] for row in rows
            ]
            await transaction.execute_many(statement, values)
            if postgres and types.get("id") in {"integer", "bigint", "smallint"}:
                await transaction.execute_query(
                    "SELECT setval(pg_get_serial_sequence($1, 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {_quote(table)}",
                    [table],
                )

    async def drop_all(self) -> None:
        async with self._connection() as connection:
            tables = await self._tables(connection)
            if connection.capabilities.dialect != "sqlite":
                async with connection._in_transaction() as transaction:
                    for table in tables:
                        await transaction.execute_query(f"DROP TABLE {_quote(table)} CASCADE")
            else:
                async with ForeignKeyDisabler(connection, connection.capabilities.dialect, logger=self.logger):
                    for table in tables:
                        await connection.execute_script(f"DROP TABLE {_quote(table)};")
