"""Tortoise ORM connection settings and start-up / shut-down."""

from typing import Any

from tortoise import Tortoise

from mealie.core.config import get_app_settings

MODELS_MODULE = "mealie.db.tortoise.models"


def tortoise_db_url(sqlalchemy_url: str) -> str:
    """Translates Mealie's SQLAlchemy-style database URL into Tortoise's format."""
    if sqlalchemy_url.startswith("sqlite:///"):
        # SQLAlchemy uses sqlite:////abs/path; Tortoise uses sqlite:///abs/path
        return "sqlite://" + sqlalchemy_url.removeprefix("sqlite:///")
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if sqlalchemy_url.startswith(prefix):
            return "asyncpg://" + sqlalchemy_url.removeprefix(prefix)
    raise ValueError("Unsupported database URL for Tortoise ORM")


def _sqlite_connection(url: str) -> dict[str, Any]:
    """SQLite pragmas that match what mealie.db.db_setup sets for SQLAlchemy connections.

    Tortoise defaults to journal_mode=WAL. Left alone, it would switch every user's database to
    WAL (which Mealie only does when SQLITE_MIGRATE_JOURNAL_WAL is set), and changing the
    journal mode while SQLAlchemy is connected fails with "database is locked".
    Foreign keys stay on, as Tortoise sets them, so SQLite behaves like PostgreSQL.
    """
    settings = get_app_settings()
    pragmas: dict[str, Any] = {"foreign_keys": "ON"}
    if settings.SQLITE_MIGRATE_JOURNAL_WAL:
        pragmas["journal_mode"] = "WAL"
    elif settings.TESTING:
        pragmas["journal_mode"] = "MEMORY"
    else:
        pragmas["journal_mode"] = "DELETE"
    if settings.TESTING:
        pragmas["synchronous"] = "OFF"
    return {
        "engine": "tortoise.backends.sqlite",
        "credentials": {"file_path": url.removeprefix("sqlite://"), **pragmas},
    }


def tortoise_config() -> dict[str, Any]:
    settings = get_app_settings()
    url = tortoise_db_url(settings.DB_URL)  # type: ignore[arg-type]
    connection: str | dict[str, Any] = _sqlite_connection(url) if url.startswith("sqlite://") else url
    return {
        "connections": {"default": connection},
        "apps": {"models": {"models": [MODELS_MODULE, "aerich.models"], "default_connection": "default"}},
        # datetimes are handled by NaiveUTCDatetimeField, not by Tortoise's timezone support
        "use_tz": False,
        "timezone": "UTC",
    }


async def init_tortoise() -> None:
    # The app lifespan runs in its own task, separate from the tasks that handle requests.
    # Tortoise 1.x keeps its state in a context variable, so it has to be told to also keep a
    # global fallback, otherwise requests see "No TortoiseContext is currently active".
    await Tortoise.init(config=tortoise_config(), _enable_global_fallback=True)


async def close_tortoise() -> None:
    await Tortoise.close_connections()
