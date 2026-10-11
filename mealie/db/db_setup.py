"""Access the async connection owned by the current database context."""

from collections.abc import Iterator
from contextlib import contextmanager

from tortoise import connections
from tortoise.backends.base.client import BaseDBAsyncClient


@contextmanager
def session_context() -> Iterator[BaseDBAsyncClient]:
    """Borrow the active connection without starting a separate transaction.

    The enclosing database_context owns its lifetime. Atomic operations use
    tortoise.transactions.in_transaction on this same event loop.
    """
    yield connections.get("default")


async def generate_session() -> BaseDBAsyncClient:
    """Provide the active connection to async FastAPI dependencies."""
    return connections.get("default")
