"""Async database lifecycle and request-scoped connection dependencies."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs, urlsplit

from tortoise import Tortoise, connections
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.backends.base.config_generator import expand_db_url

from mealie.core.config import get_app_settings
from mealie.core.settings.db_providers import SQLiteProvider


def native_connection_config(url: str) -> dict[str, Any]:
    """Translate the existing application URL format to native driver settings."""
    if url.startswith("sqlite:////"):
        url = "sqlite://" + url.removeprefix("sqlite:///")
    elif url.startswith("postgresql://"):
        url = "postgres://" + url.removeprefix("postgresql://")
    config = expand_db_url(url)
    if config["engine"] == "tortoise.backends.asyncpg":
        credentials = config["credentials"]
        parameters = parse_qs(urlsplit(url).query)
        # URL query hosts also support Unix sockets; Tortoise's URL parser
        # replaces these with the (possibly absent) hostname from the authority.
        if "host" in parameters:
            credentials["host"] = parameters["host"][-1]
        if "sslmode" in credentials:
            credentials["ssl"] = credentials.pop("sslmode")
        if "connect_timeout" in credentials:
            credentials["timeout"] = float(credentials.pop("connect_timeout"))
    return config


def database_config(db_url: str | None = None) -> dict[str, Any]:
    settings = get_app_settings()
    url = db_url or settings.DB_URL
    if not url:
        raise ValueError("No database URL configured")
    connection: dict[str, Any] = native_connection_config(url)
    if settings.DB_ENGINE == "sqlite" and db_url is None:
        provider = settings.DB_PROVIDER
        if not isinstance(provider, SQLiteProvider):
            raise ValueError("SQLite database provider is not configured")
        credentials: dict[str, Any] = {
            "file_path": str(provider.db_path),
            "foreign_keys": "ON",
            "journal_mode": "WAL" if settings.SQLITE_MIGRATE_JOURNAL_WAL else "DELETE",
            "busy_timeout": 30000,
        }
        if settings.TESTING:
            credentials["synchronous"] = "OFF"
            if not settings.SQLITE_MIGRATE_JOURNAL_WAL:
                credentials["journal_mode"] = "MEMORY"
        connection = {"engine": "tortoise.backends.sqlite", "credentials": credentials}
    return {
        "connections": {"default": connection},
        "apps": {
            "models": {
                "models": ["mealie.db.models._all_models", "aerich.models"],
                "default_connection": "default",
            }
        },
        "use_tz": False,
        "timezone": "UTC",
    }


# Aerich imports configuration without starting an event loop or opening a connection.
TORTOISE_ORM = database_config()


async def initialize_database(db_url: str | None = None) -> None:
    await Tortoise.init(config=database_config(db_url))


async def close_database() -> None:
    await Tortoise.close_connections()


@asynccontextmanager
async def session_context() -> AsyncIterator[BaseDBAsyncClient]:
    """Borrow the application connection; repository writes own their transactions.

    Connections belong to the application lifecycle. A request must never close
    the shared SQLite connection or PostgreSQL connection pool.
    """
    yield connections.get("default")


async def generate_session() -> AsyncIterator[BaseDBAsyncClient]:
    """FastAPI dependency sharing the same lifecycle as background database tasks."""
    async with session_context() as connection:
        yield connection
