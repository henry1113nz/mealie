"""SQLite backend that preserves Mealie's opt-in journal mode changes."""

import sqlite3
from typing import Any

from tortoise.backends.base.client import NestedTransactionContext, TransactionContext
from tortoise.backends.sqlite.client import (
    SqliteClient,
    SqliteTransactionContext,
    SqliteTransactionWrapper,
    translate_exceptions,
)

from mealie.db.schema_generator import MealieSqliteSchemaGenerator


class MealieSqliteTransactionWrapper(SqliteTransactionWrapper):
    schema_generator = MealieSqliteSchemaGenerator

    def _in_transaction(self) -> TransactionContext:
        return NestedTransactionContext(MealieSqliteTransactionWrapper(self))

    @translate_exceptions
    async def execute_script(self, query: str) -> None:
        # sqlite3.executescript implicitly commits an existing transaction.
        # Execute complete statements individually so Aerich's schema changes
        # and its migration ledger commit together, including on failure.
        async with self.acquire_connection() as connection:
            statement = ""
            for character in query:
                statement += character
                if character == ";" and sqlite3.complete_statement(statement):
                    await connection.execute(statement)
                    statement = ""
            if statement.strip():
                await connection.execute(statement)


class MealieSqliteClient(SqliteClient):
    schema_generator = MealieSqliteSchemaGenerator

    def __init__(self, file_path: str, **kwargs: Any) -> None:
        super().__init__(file_path, **kwargs)
        # Tortoise defaults to setting WAL on every connection. When Mealie's
        # setting is off, leave the existing persistent journal mode untouched.
        if "journal_mode" not in kwargs:
            self.pragmas.pop("journal_mode", None)

    def _in_transaction(self) -> TransactionContext:
        return SqliteTransactionContext(MealieSqliteTransactionWrapper(self), self._lock)


client_class = MealieSqliteClient
