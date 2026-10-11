"""PostgreSQL backend that preserves Mealie's connection URL overrides."""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import asyncpg
from tortoise.backends.asyncpg.client import AsyncpgDBClient

from mealie.db.schema_generator import MealiePostgresSchemaGenerator


class MealieAsyncpgClient(AsyncpgDBClient):
    schema_generator = MealiePostgresSchemaGenerator

    def __init__(self, *, dsn: str | None = None, **kwargs: Any) -> None:
        # The upstream client logs self.extra inside its connection template.
        # Keep the URL, which may contain a password, out of that template.
        self._dsn = dsn
        super().__init__(**kwargs)

    async def create_pool(self, **kwargs: Any) -> asyncpg.Pool:
        dsn = self._dsn
        if dsn is None:
            return await super().create_pool(**kwargs)

        # Tortoise supplies a default port and empty credentials even when the
        # configured DSN owns them. Let asyncpg parse ports, sockets, TLS options,
        # and escaped credentials without these keyword arguments overriding it.
        for name in ("host", "port", "user", "password", "database"):
            kwargs.pop(name, None)

        parsed = urlsplit(dsn)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        timeouts = [value for name, value in query if name == "connect_timeout"]
        if timeouts:
            # asyncpg otherwise sends this libpq client option to PostgreSQL as
            # an unknown server setting. Zero and negative values mean no limit.
            seconds = int(timeouts[-1] or "0")
            kwargs.setdefault("timeout", seconds if seconds > 0 else None)
            query = [(name, value) for name, value in query if name != "connect_timeout"]
            dsn = parsed._replace(query=urlencode(query)).geturl()

        return await asyncpg.create_pool(dsn, **kwargs)


client_class = MealieAsyncpgClient
