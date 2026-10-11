"""Configuration shared by the async application and Aerich migrations."""

from typing import Any

from mealie.core.config import get_app_settings
from mealie.core.settings import AppSettings
from mealie.core.settings.db_providers import PostgresProvider, SQLiteProvider

# Register domain models explicitly, separately from Aerich's migration ledger.
TORTOISE_MODEL_MODULES: tuple[str, ...] = (
    "mealie.db.models.server.task",
    "mealie.db.models.users.users",
    "mealie.db.models.users.password_reset",
    "mealie.db.models.users.user_to_recipe",
    "mealie.db.models.group.group",
    "mealie.db.models.group.preferences",
    "mealie.db.models.group.ai_providers",
    "mealie.db.models.group.exports",
    "mealie.db.models.group.report",
    "mealie.db.models.household.household",
    "mealie.db.models.household.preferences",
    "mealie.db.models.household.cookbook",
    "mealie.db.models.household.events",
    "mealie.db.models.household.household_to_recipe",
    "mealie.db.models.household.invite_tokens",
    "mealie.db.models.household.mealplan",
    "mealie.db.models.household.recipe_action",
    "mealie.db.models.household.shopping_list",
    "mealie.db.models.household.webhooks",
    "mealie.db.models.recipe.api_extras",
    "mealie.db.models.recipe.assets",
    "mealie.db.models.recipe.category",
    "mealie.db.models.recipe.comment",
    "mealie.db.models.recipe.ingredient",
    "mealie.db.models.recipe.instruction",
    "mealie.db.models.recipe.labels",
    "mealie.db.models.recipe.note",
    "mealie.db.models.recipe.nutrition",
    "mealie.db.models.recipe.recipe",
    "mealie.db.models.recipe.recipe_timeline",
    "mealie.db.models.recipe.settings",
    "mealie.db.models.recipe.shared",
    "mealie.db.models.recipe.tag",
    "mealie.db.models.recipe.tool",
)
DEFAULT_CONNECTION = "default"
MIGRATION_MODEL_MODULES: tuple[str, ...] = ("aerich.models",)


def get_tortoise_config(settings: AppSettings | None = None) -> dict[str, Any]:
    """Use the same database and credentials as the existing application."""
    settings = settings if settings is not None else get_app_settings()
    provider = settings.DB_PROVIDER
    if isinstance(provider, SQLiteProvider):
        credentials: dict[str, Any] = {"file_path": str(provider.db_path.absolute())}
        if settings.SQLITE_MIGRATE_JOURNAL_WAL:
            credentials["journal_mode"] = "WAL"
        elif settings.TESTING:
            credentials["journal_mode"] = "MEMORY"
        if settings.TESTING:
            credentials["synchronous"] = "OFF"
        connection = {"engine": "mealie.db.tortoise_sqlite", "credentials": credentials}
    elif isinstance(provider, PostgresProvider):
        # Let asyncpg interpret the existing DSN, including libpq options such as
        # sslmode. Tortoise's URL parser has different schemes/query semantics.
        if provider.POSTGRES_URL_OVERRIDE:
            credentials = {"dsn": provider.db_url}
        else:
            credentials = {
                "host": provider.POSTGRES_SERVER,
                "port": int(provider.POSTGRES_PORT),
                "user": provider.POSTGRES_USER,
                "password": provider.POSTGRES_PASSWORD,
                "database": provider.POSTGRES_DB,
            }
        connection = {"engine": "mealie.db.tortoise_postgres", "credentials": credentials}
    else:
        raise ValueError("Tortoise requires a SQLite or PostgreSQL database provider")

    apps: dict[str, Any] = {
        "models": {"models": list(TORTOISE_MODEL_MODULES), "default_connection": DEFAULT_CONNECTION},
    }
    if MIGRATION_MODEL_MODULES:
        apps["migrations"] = {"models": list(MIGRATION_MODEL_MODULES), "default_connection": DEFAULT_CONNECTION}
    return {
        "connections": {DEFAULT_CONNECTION: connection},
        "apps": apps,
        "use_tz": True,
        "timezone": "UTC",
    }
