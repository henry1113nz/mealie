"""Async database ownership for application lifespans, scripts, and tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from tortoise.context import TortoiseContext

from mealie.db.tortoise_config import get_tortoise_config


@asynccontextmanager
async def database_context(
    config: dict[str, Any] | None = None, *, global_fallback: bool = False
) -> AsyncIterator[TortoiseContext]:
    """Own connections on one event loop, including cleanup on startup failure.

    Only the FastAPI lifespan enables the global fallback: ASGI request tasks
    need access to the context created in the separate lifespan task. Scripts
    and tests use isolated contexts. This does not create tables or migrate data.
    """
    async with TortoiseContext() as context:
        await context.init(
            config=config if config is not None else get_tortoise_config(),
            _enable_global_fallback=global_fallback,
        )
        # Open before the health query so startup connection errors retain the
        # driver's exception instead of being translated into query errors.
        client = context.db()
        await client.create_connection(with_db=True)
        await client.execute_query("SELECT 1")
        yield context
