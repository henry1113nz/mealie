"""Run synchronous test database setup on the application's owning event loop.

Production repositories remain async. Existing synchronous HTTP tests share the
TestClient portal, so every converted repository uses the same connections and
loop as the requests it prepares data for.
"""

import asyncio
import inspect
from collections.abc import Awaitable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any

from anyio.from_thread import BlockingPortal
from pydantic import UUID4
from sqlalchemy.orm import Session

from mealie.repos._utils import NOT_SET, NotSet
from mealie.repos.repository_factory import AllRepositories

_portal: BlockingPortal | None = None
_portal_loop: asyncio.AbstractEventLoop | None = None


@contextmanager
def use_database_portal(portal: BlockingPortal) -> Iterator[None]:
    global _portal, _portal_loop
    _portal = portal
    _portal_loop = portal.call(asyncio.get_running_loop)
    try:
        yield
    finally:
        _portal = None
        _portal_loop = None


async def _await_result[T](awaitable: Awaitable[T]) -> T:
    return await awaitable


def run_async[T](awaitable: Awaitable[T]) -> T:
    if _portal is None:
        raise RuntimeError("Async database setup requires the api_client fixture")
    return _portal.call(_await_result, awaitable)


class SynchronousRepository:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.repository, name)
        if not callable(value):
            return value

        @wraps(value)
        def call(*args: Any, **kwargs: Any) -> Any:
            result = value(*args, **kwargs)
            if inspect.isawaitable(result):
                try:
                    on_database_loop = asyncio.get_running_loop() is _portal_loop
                except RuntimeError:
                    on_database_loop = False
                return result if on_database_loop else run_async(result)
            if isinstance(result, type(self.repository)):
                return SynchronousRepository(result)
            return result

        return call


class SynchronousRepositories(AllRepositories):
    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        if name in {
            "households",
            "household_preferences",
            "household_recipes",
            "cookbooks",
            "group_invite_tokens",
            "group_recipe_actions",
            "meals",
            "group_meal_plan_rules",
            "group_shopping_lists",
            "group_shopping_list_item",
            "group_shopping_list_item_references",
            "group_shopping_list_recipe_refs",
            "shopping_list_multi_purpose_labels",
            "group_event_notifier",
            "webhooks",
            "users",
            "user_ratings",
            "api_tokens",
            "tokens_pw_reset",
            "groups",
            "group_preferences",
            "group_exports",
            "group_reports",
            "group_report_entries",
            "group_ai_providers",
            "group_ai_provider_settings",
        }:
            return SynchronousRepository(value)
        return value


def get_repositories(
    session: Session,
    *,
    group_id: UUID4 | None | NotSet = NOT_SET,
    household_id: UUID4 | None | NotSet = NOT_SET,
) -> AllRepositories:
    return SynchronousRepositories(session, group_id=group_id, household_id=household_id)
