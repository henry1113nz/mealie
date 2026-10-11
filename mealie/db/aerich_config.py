"""Importable Aerich CLI configuration, using the application's settings."""

from mealie.db.tortoise_config import get_tortoise_config

TORTOISE_ORM = get_tortoise_config()
