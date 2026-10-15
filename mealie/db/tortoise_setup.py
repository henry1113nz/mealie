"""Isolated async database lifecycle for the incremental Tortoise migration.

The application continues to use its legacy database lifecycle until later
migration stages switch runtime callers over to Tortoise.
"""

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, status
from tortoise import Tortoise
from tortoise.backends.base.config_generator import expand_db_url

from mealie.core.config import get_app_settings


def tortoise_config(db_url: str | None = None) -> dict[str, Any]:
    """Build a Tortoise config without initializing connections or models."""
    if db_url is None:
        settings = get_app_settings()
        provider = settings.DB_PROVIDER
        if provider is None:
            raise ValueError("Database provider is not configured")
        db_url = provider.tortoise_db_url

    connection = expand_db_url(db_url)
    backend = connection["engine"].rsplit(".", maxsplit=1)[-1]
    if backend in {"sqlite", "asyncpg"}:
        connection["engine"] = f"mealie.db.tortoise_backends.{backend}"
    if backend == "sqlite":
        settings = get_app_settings()
        if settings.TESTING:
            connection["credentials"]["journal_mode"] = "WAL" if settings.SQLITE_MIGRATE_JOURNAL_WAL else "MEMORY"

    return {
        "connections": {"default": connection},
        "apps": {
            "models": {
                "models": ["mealie.db.tortoise_models", "aerich.models"],
                "default_connection": "default",
            }
        },
        "use_tz": True,
        "timezone": "UTC",
    }


async def tortoise_init(db_url: str | None = None, *, create_schema: bool = False) -> None:
    """Initialize an isolated Tortoise connection set.

    ``create_schema`` is available for smoke checks and future migration
    stages; this stage intentionally defines no production placeholder models.
    """
    if db_url and db_url.startswith("sqlite://"):
        Path(db_url.removeprefix("sqlite://")).parent.mkdir(parents=True, exist_ok=True)
    await Tortoise.init(config=tortoise_config(db_url))
    if create_schema:
        await Tortoise.generate_schemas(safe=True)


async def tortoise_close() -> None:
    """Close all initialized Tortoise connections."""
    await Tortoise.close_connections()


async def require_tortoise_ready(request: Request) -> None:
    """Guard converted routes against lifespan bypass or failed initialization."""
    if not getattr(request.app.state, "tortoise_ready", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async database is not initialized",
        )
