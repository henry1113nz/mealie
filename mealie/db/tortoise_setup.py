"""Tortoise ORM configuration and lifecycle helpers."""

from typing import Any

from tortoise import Tortoise

from mealie.core.config import get_app_settings


def get_tortoise_config() -> dict[str, Any]:
    settings = get_app_settings()
    database_url = settings.DB_URL
    if database_url is None:
        raise ValueError("No database URL is configured")

    if settings.DB_ENGINE == "sqlite":
        return {
            "connections": {
                "default": {
                    "engine": "tortoise.backends.sqlite",
                    "credentials": {
                        "file_path": str(settings.DB_PROVIDER.db_path),
                        "journal_mode": (
                            "MEMORY"
                            if settings.TESTING and not settings.SQLITE_MIGRATE_JOURNAL_WAL
                            else "WAL"
                            if settings.SQLITE_MIGRATE_JOURNAL_WAL
                            else "DELETE"
                        ),
                        **({"synchronous": "OFF"} if settings.TESTING else {}),
                    },
                }
            },
            "apps": {
                "models": {
                    "models": ["mealie.db.models.tortoise_models", "aerich.models"],
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "timezone": "UTC",
        }

    # Tortoise uses `postgres://` as the async PostgreSQL connection scheme.
    if database_url.startswith("postgresql://"):
        database_url = "postgres://" + database_url.removeprefix("postgresql://")

    return {
        "connections": {"default": database_url},
        "apps": {
            "models": {
                "models": ["mealie.db.models.tortoise_models", "aerich.models"],
                "default_connection": "default",
            }
        },
        "use_tz": False,
        "timezone": "UTC",
    }


TORTOISE_ORM = get_tortoise_config()


async def init_database() -> None:
    """Initialize Tortoise for the application lifespan."""
    await Tortoise.init(config=get_tortoise_config())


async def close_database() -> None:
    """Close all Tortoise connections during application shutdown."""
    await Tortoise.close_connections()
