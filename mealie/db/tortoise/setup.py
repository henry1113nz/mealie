from tortoise import Tortoise

from mealie.core.root_logger import get_logger
from mealie.db.tortoise.config import get_tortoise_config

logger = get_logger()


async def init_tortoise(config: dict | None = None, generate_schemas: bool = False) -> None:
    """Initialize Tortoise ORM connections."""
    if Tortoise._inited:
        return
    if config is None:
        config = get_tortoise_config()
    await Tortoise.init(config=config)
    if generate_schemas:
        await Tortoise.generate_schemas()
    logger.info("Tortoise ORM initialized.")


async def close_tortoise() -> None:
    """Close Tortoise ORM connections."""
    if Tortoise._inited:
        await Tortoise.close_connections()
        logger.info("Tortoise ORM connections closed.")
