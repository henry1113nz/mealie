from typing import Any

from mealie.core.config import get_app_settings


def get_db_url(db_url: str | None = None) -> str:
    """Return the database URL formatted for Tortoise ORM / async drivers."""
    if db_url:
        url = db_url
    else:
        settings = get_app_settings()
        url = settings.DB_URL or ""

    # asyncpg expects 'postgres://' or 'postgresql://'
    return url


def get_tortoise_config(
    db_url: str | None = None,
    models_list: list[str] | None = None,
) -> dict[str, Any]:
    """Generate the Tortoise ORM configuration dictionary."""
    url = get_db_url(db_url)
    if models_list is None:
        models_list = ["mealie.db.tortoise.models"]

    return {
        "connections": {
            "default": url,
        },
        "apps": {
            "models": {
                "models": models_list,
                "default_connection": "default",
            },
        },
    }


TORTOISE_ORM = get_tortoise_config()
