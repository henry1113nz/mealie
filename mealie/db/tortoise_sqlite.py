"""SQLite backend that preserves Mealie's opt-in journal mode changes."""

from typing import Any

from tortoise.backends.sqlite.client import SqliteClient


class MealieSqliteClient(SqliteClient):
    def __init__(self, file_path: str, **kwargs: Any) -> None:
        super().__init__(file_path, **kwargs)
        # Tortoise defaults to setting WAL on every connection. When Mealie's
        # setting is off, leave the existing persistent journal mode untouched.
        if "journal_mode" not in kwargs:
            self.pragmas.pop("journal_mode", None)


client_class = MealieSqliteClient
