"""Tortoise connection settings, start-up and shut-down (stage S1 of REWRITE_PLAN.md)."""

from typing import Any

from tortoise import Tortoise

from mealie.core.config import get_app_settings


def _connection() -> str | dict[str, Any]:
    settings = get_app_settings()
    url: str = settings.DB_URL  # type: ignore[assignment]
    if url.startswith("sqlite:///"):
        # Same pragmas as mealie/db/db_setup.py gives SQLAlchemy. Tortoise would otherwise switch
        # the file to WAL, which Mealie only does when SQLITE_MIGRATE_JOURNAL_WAL is set.
        if settings.SQLITE_MIGRATE_JOURNAL_WAL:
            journal = "WAL"
        elif settings.TESTING:
            journal = "MEMORY"
        else:
            journal = "DELETE"
        credentials: dict[str, Any] = {"file_path": url.removeprefix("sqlite:///"), "journal_mode": journal}
        if settings.TESTING:
            credentials["synchronous"] = "OFF"
        return {"engine": "tortoise.backends.sqlite", "credentials": credentials}
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "asyncpg://" + url.removeprefix(prefix)
    raise ValueError("unsupported database URL for Tortoise ORM")


def tortoise_config() -> dict[str, Any]:
    return {
        "connections": {"default": _connection()},
        "apps": {"models": {"models": ["mealie.db.tortoise.models", "aerich.models"], "default_connection": "default"}},
        "use_tz": False,
        "timezone": "UTC",
    }


async def init_tortoise() -> None:
    # the lifespan runs in its own task, so requests need the global fallback context
    await Tortoise.init(config=tortoise_config(), _enable_global_fallback=True)


async def close_tortoise() -> None:
    await Tortoise.close_connections()
