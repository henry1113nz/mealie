"""Database helpers execute test setup on the application's async event loop."""

import asyncio
from collections.abc import Awaitable, Generator
from contextlib import contextmanager

import pytest
from anyio.from_thread import BlockingPortal
from tortoise import connections
from tortoise.backends.base.client import BaseDBAsyncClient

from mealie.repos.all_repositories import AllRepositories, get_repositories

_portal: BlockingPortal | None = None


async def _resolve[T](value: Awaitable[T]) -> T:
    return await value


def run_db[T](value: Awaitable[T]) -> T:
    """Run a database operation on the TestClient's persistent application loop."""
    if _portal is None:
        raise RuntimeError("Database access requires the api_client fixture")
    return _portal.call(_resolve, value)


async def await_db[T](value: Awaitable[T]) -> T:
    """Bridge an async test's event loop to the application's connection pool."""
    if _portal is None:
        raise RuntimeError("Database access requires the api_client fixture")
    return await asyncio.wrap_future(_portal.start_task_soon(_resolve, value))


@contextmanager
def session_context() -> Generator[BaseDBAsyncClient]:
    """Borrow the app connection for synchronous test database setup."""
    if _portal is None:
        raise RuntimeError("Database access requires the api_client fixture")
    yield _portal.call(connections.get, "default")


@pytest.fixture(scope="module")
def session(api_client) -> Generator[BaseDBAsyncClient]:
    assert api_client.portal is not None
    yield api_client.portal.call(connections.get, "default")


@pytest.fixture()
def unfiltered_database(session: BaseDBAsyncClient) -> Generator[AllRepositories]:
    yield get_repositories(session, group_id=None, household_id=None)
