"""Portable backups through the application's async database connection."""

import datetime
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi.encoders import jsonable_encoder
from tortoise import connections
from tortoise.backends.base.client import BaseDBAsyncClient, TransactionalDBClient
from tortoise.transactions import in_transaction

from mealie.db import init_db
from mealie.services._base_service import BaseService


class BackupSchemaMismatch(Exception):
    """The archive was created with a different database schema."""


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


@dataclass
class BackupColumn:
    name: str
    type: str
    nullable: bool
    primary_key: bool = False
    sequence: bool = False
    default: Any = None


@dataclass
class BackupForeignKey:
    column: str
    table: str
    target: str


@dataclass
class BackupTable:
    name: str
    columns: dict[str, BackupColumn] = field(default_factory=dict)
    foreign_keys: list[BackupForeignKey] = field(default_factory=list)


class TortoiseExporter(BaseService):
    look_for_datetime = {
        "created_at",
        "update_at",
        "date_updated",
        "timestamp",
        "expires_at",
        "locked_at",
        "last_made",
        "completed_date",
        "tokens_valid_after",
    }
    look_for_date = {"date_added", "date"}
    look_for_time = {"scheduled_time"}

    def __init__(self, connection_str: str | None = None) -> None:
        super().__init__()
        # The owning database_context selects the connection. No exporter-owned
        # pool or event loop is created, including when a transaction is active.
        self.connection_str = connection_str

    @staticmethod
    def _postgres(connection: BaseDBAsyncClient) -> bool:
        return connection.capabilities.dialect == "postgres"

    @classmethod
    def _parameter(cls, connection: BaseDBAsyncClient, index: int) -> str:
        return f"${index}" if cls._postgres(connection) else "?"

    async def _tables(self, connection: BaseDBAsyncClient) -> dict[str, BackupTable]:
        tables: dict[str, BackupTable] = {}
        if not self._postgres(connection):
            names = await connection.execute_query_dict(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            for item in names:
                name = item["name"]
                table = tables[name] = BackupTable(name)
                for column in await connection.execute_query_dict(f"PRAGMA table_info({_quote(name)})"):
                    table.columns[column["name"]] = BackupColumn(
                        column["name"], column["type"].lower(), not bool(column["notnull"]), bool(column["pk"]),
                        default=column.get("dflt_value"),
                    )
                for fk in await connection.execute_query_dict(f"PRAGMA foreign_key_list({_quote(name)})"):
                    table.foreign_keys.append(BackupForeignKey(fk["from"], fk["table"], fk["to"]))
            return tables

        columns = await connection.execute_query_dict(
            """SELECT c.table_name, c.column_name, c.data_type, c.is_nullable, c.column_default,
                      EXISTS (SELECT 1 FROM information_schema.table_constraints tc
                              JOIN information_schema.key_column_usage kcu
                                ON kcu.constraint_name = tc.constraint_name
                               AND kcu.constraint_schema = tc.constraint_schema
                               AND kcu.table_name = tc.table_name
                              WHERE tc.constraint_type = 'PRIMARY KEY'
                                AND tc.table_schema = c.table_schema
                                AND tc.table_name = c.table_name
                                AND kcu.column_name = c.column_name) AS primary_key
               FROM information_schema.columns c
               JOIN information_schema.tables t
                 ON t.table_schema = c.table_schema AND t.table_name = c.table_name
               WHERE c.table_schema = current_schema() AND t.table_type = 'BASE TABLE'
               ORDER BY c.table_name, c.ordinal_position"""
        )
        for column in columns:
            name = column["table_name"]
            table = tables.setdefault(name, BackupTable(name))
            table.columns[column["column_name"]] = BackupColumn(
                column["column_name"],
                column["data_type"],
                column["is_nullable"] == "YES",
                column["primary_key"],
                str(column["column_default"] or "").startswith("nextval("),
            )
        foreign_keys = await connection.execute_query_dict(
            """SELECT tc.table_name, kcu.column_name, ccu.table_name AS target_table,
                      ccu.column_name AS target_column
               FROM information_schema.table_constraints tc
               JOIN information_schema.key_column_usage kcu
                 ON kcu.constraint_name = tc.constraint_name AND kcu.constraint_schema = tc.constraint_schema
               JOIN information_schema.constraint_column_usage ccu
                 ON ccu.constraint_name = tc.constraint_name AND ccu.constraint_schema = tc.constraint_schema
               WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = current_schema()"""
        )
        for fk in foreign_keys:
            tables[fk["table_name"]].foreign_keys.append(
                BackupForeignKey(fk["column_name"], fk["target_table"], fk["target_column"])
            )
        return tables

    @staticmethod
    def _versions(data: dict[str, list[dict[str, Any]]]) -> set[tuple[str, str]]:
        return {(row["app"], row["version"]) for row in data.get("aerich", [])}

    async def dump_schema(self) -> dict[str, list[dict[str, Any]]]:
        async with in_transaction("default") as connection:
            tables = await self._tables(connection)
            result: dict[str, list[dict[str, Any]]] = {name: [] for name in tables}
            if "aerich" in tables:
                result["aerich"] = await connection.execute_query_dict('SELECT * FROM "aerich" ORDER BY "id"')
            return jsonable_encoder(result)

    async def dump(self) -> dict[str, list[dict[str, Any]]]:
        """Read one consistent database snapshot, including join tables and Aerich."""
        # A nested export uses its caller's isolation level and uncommitted data.
        nested = isinstance(connections.get("default"), TransactionalDBClient)
        async with in_transaction("default") as connection:
            if self._postgres(connection) and not nested:
                await connection.execute_query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            tables = await self._tables(connection)
            result = {name: await connection.execute_query_dict(f"SELECT * FROM {_quote(name)}") for name in tables}
            return jsonable_encoder(result)

    def _convert_value(self, value: Any, column: BackupColumn, *, postgres: bool) -> Any:
        if value is None:
            return None
        kind = column.type
        if kind in {"json", "jsonb"}:
            return value if isinstance(value, str) else json.dumps(value)
        if postgres:
            if kind == "uuid":
                return uuid.UUID(str(value))
            if kind in {"timestamp without time zone", "timestamp with time zone"}:
                value = datetime.datetime.fromisoformat(value) if isinstance(value, str) else value
                if value.tzinfo is not None:
                    value = value.astimezone(datetime.UTC)
                return value.replace(tzinfo=None) if kind == "timestamp without time zone" else value
            if kind == "date" and isinstance(value, str):
                return datetime.date.fromisoformat(value)
            if kind.startswith("time ") and isinstance(value, str):
                return datetime.time.fromisoformat(value)
            if kind == "boolean":
                return bool(value)
        else:
            # Native PostgreSQL UUIDs are serialized with hyphens; SQLite uses
            # the existing compact UUID storage. Convert only UUID columns.
            if kind in {"char(32)", "uuid"}:
                return uuid.UUID(str(value)).hex
            if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                return value.isoformat()
        return value

    @staticmethod
    def _ordered_tables(tables: dict[str, BackupTable]) -> tuple[list[str], dict[str, set[str]]]:
        """Defer only nullable references which actually break a reference cycle.

        Acyclic nullable references can participate in CHECK constraints, such as
        a substitution which requires either a food or a note. Those references
        must retain their values throughout deletion and insertion.
        """
        remaining = {
            name: {fk.table for fk in table.foreign_keys if fk.table in tables} for name, table in tables.items()
        }
        ordered: list[str] = []
        deferred: dict[str, set[str]] = {name: set() for name in tables}

        def find_cycle(name: str, path: list[str], visited: set[str]) -> list[str] | None:
            if name in path:
                return [*path[path.index(name) :], name]
            if name in visited:
                return None
            visited.add(name)
            for dependency in sorted(remaining[name]):
                if cycle := find_cycle(dependency, [*path, name], visited):
                    return cycle
            return None

        while remaining:
            ready = [name for name, dependencies in remaining.items() if not dependencies]
            if not ready:
                visited: set[str] = set()
                cycle = next(cycle for name in remaining if (cycle := find_cycle(name, [], visited)) is not None)
                for name, dependency in zip(cycle, cycle[1:], strict=False):
                    references = [fk.column for fk in tables[name].foreign_keys if fk.table == dependency]
                    if all(tables[name].columns[column].nullable for column in references):
                        deferred[name].update(references)
                        remaining[name].remove(dependency)
                        break
                else:
                    raise ValueError("Backup schema contains a cycle of required foreign keys")
                continue
            ordered.extend(ready)
            for name in ready:
                del remaining[name]
            for dependencies in remaining.values():
                dependencies.difference_update(ready)
        return ordered, deferred

    async def _clear(self, connection: BaseDBAsyncClient, order: list[str], deferred: dict[str, set[str]]) -> None:
        # Break the nullable recipe/user and AI selection cycles while retaining
        # all constraints. This requires neither SQLite PRAGMAs nor PostgreSQL
        # superuser privileges, and rolls back together with the row replacement.
        for name, nullable in deferred.items():
            if nullable:
                assignments = ", ".join(f"{_quote(column)} = NULL" for column in nullable)
                await connection.execute_query(f"UPDATE {_quote(name)} SET {assignments}")
        for name in reversed(order):
            await connection.execute_query(f"DELETE FROM {_quote(name)}")

    async def restore(self, db_dump: dict[str, list[dict[str, Any]]]) -> None:
        """Replace data atomically, preserving constraints and the migration schema."""
        # A caller may explicitly have dropped a disposable database's tables.
        # Normal restores never drop the schema or its currently applied version.
        await init_db.prepare_database()
        async with in_transaction("default") as connection:
            all_tables = await self._tables(connection)
            if self._postgres(connection):
                # Serialize a database replacement with live application writes.
                # SQLite already serializes writes on its transaction connection.
                table_names = ", ".join(_quote(name) for name in sorted(all_tables))
                await connection.execute_query(f"LOCK TABLE {table_names} IN ACCESS EXCLUSIVE MODE")
            current_versions = await connection.execute_query_dict('SELECT "app", "version" FROM "aerich"')
            if not self._versions(db_dump) or self._versions(db_dump) != self._versions({"aerich": current_versions}):
                raise BackupSchemaMismatch("Database backup schema version does not match current database")
            if set(db_dump) != set(all_tables):
                raise BackupSchemaMismatch("Database backup tables do not match current database")
            tables = {name: table for name, table in all_tables.items() if name != "aerich"}
            order, deferred_columns = self._ordered_tables(tables)
            data: dict[str, list[dict[str, Any]]] = {}
            for name, table in tables.items():
                data[name] = []
                for row in db_dump[name]:
                    if set(row) - set(table.columns):
                        raise BackupSchemaMismatch(f"Unknown columns in backup table {name}")
                    data[name].append(
                        {
                            key: self._convert_value(value, table.columns[key], postgres=self._postgres(connection))
                            for key, value in row.items()
                        }
                    )

            await self._clear(connection, order, deferred_columns)
            deferred: list[tuple[BackupTable, dict[str, Any], dict[str, Any]]] = []
            for name in order:
                table = tables[name]
                nullable = deferred_columns[name]
                for row in data[name]:
                    restored = dict(row)
                    refs = {key: restored[key] for key in nullable if restored.get(key) is not None}
                    if refs:
                        deferred.append((table, row, refs))
                        restored.update(dict.fromkeys(refs))
                    if not restored:
                        continue
                    columns = ", ".join(_quote(key) for key in restored)
                    placeholders = ", ".join(self._parameter(connection, i) for i in range(1, len(restored) + 1))
                    await connection.execute_query(
                        f"INSERT INTO {_quote(name)} ({columns}) VALUES ({placeholders})", list(restored.values())
                    )
            for table, row, refs in deferred:
                primary_key = {name: row[name] for name, column in table.columns.items() if column.primary_key}
                if not primary_key:
                    raise ValueError(f"Cannot restore nullable references in table {table.name} without a primary key")
                assignments = ", ".join(
                    f"{_quote(name)} = {self._parameter(connection, index)}" for index, name in enumerate(refs, 1)
                )
                conditions = " AND ".join(
                    f"{_quote(name)} = {self._parameter(connection, index)}"
                    for index, name in enumerate(primary_key, len(refs) + 1)
                )
                await connection.execute_query(
                    f"UPDATE {_quote(table.name)} SET {assignments} WHERE {conditions}",
                    [*refs.values(), *primary_key.values()],
                )
            if self._postgres(connection):
                for table in tables.values():
                    for column in table.columns.values():
                        if column.sequence:
                            sequence = await connection.execute_query_dict(
                                "SELECT n.nspname AS schema_name, c.relname AS sequence_name "
                                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                "WHERE c.oid = pg_get_serial_sequence($1, $2)::regclass",
                                [table.name, column.name],
                            )
                            maximum = await connection.execute_query_dict(
                                f"SELECT COALESCE(MAX({_quote(column.name)}), 0) + 1 AS next_value "
                                f"FROM {_quote(table.name)}"
                            )
                            # Unlike setval(), RESTART rolls back with the data
                            # replacement and blocks concurrent sequence users.
                            sequence_name = (
                                f"{_quote(sequence[0]['schema_name'])}.{_quote(sequence[0]['sequence_name'])}"
                            )
                            await connection.execute_query(
                                f"ALTER SEQUENCE {sequence_name} RESTART WITH {int(maximum[0]['next_value'])}"
                            )
            await init_db.initialize_data()

    async def drop_all(self) -> None:
        """Drop an explicitly selected database using its active async context."""
        async with in_transaction("default") as connection:
            tables = await self._tables(connection)
            order, deferred = self._ordered_tables(tables)
            await self._clear(connection, order, deferred)
            for name in reversed(order):
                suffix = " CASCADE" if self._postgres(connection) else ""
                await connection.execute_query(f"DROP TABLE {_quote(name)}{suffix}")
