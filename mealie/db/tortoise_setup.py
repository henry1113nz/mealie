"""Async database ownership for application lifespans, scripts, and tests."""

import warnings
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
        # C1 registers only an abstract base. Tortoise requires a nonempty module
        # list but warns when that module has no concrete models. Remove this
        # narrow exception with the abstract-only registry entry in C2.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=r'Module "mealie\.db\.models\._tortoise_base" has no models', category=RuntimeWarning
            )
            await context.init(
                config=config if config is not None else get_tortoise_config(),
                _enable_global_fallback=global_fallback,
            )
        await context.db().execute_query("SELECT 1")
        yield context
