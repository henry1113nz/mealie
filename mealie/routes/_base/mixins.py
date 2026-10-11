import sqlite3
from collections.abc import Callable
from logging import Logger
from typing import Any, Never

from fastapi import HTTPException, status
from pydantic import UUID4, BaseModel
from tortoise.exceptions import DoesNotExist, IntegrityError

from mealie.core.config import get_app_settings
from mealie.schema.response import ErrorResponse


def is_postgres() -> bool:
    return get_app_settings().DB_ENGINE == "postgres"


def is_unique_violation(ex: Exception) -> bool:
    """Recognize the driver's unique violation through an ORM exception."""
    original = getattr(ex, "orig", None) or ex.__cause__ or (ex.args[0] if ex.args else ex)
    if is_postgres():
        return getattr(original, "sqlstate", getattr(original, "pgcode", None)) == "23505"
    return getattr(original, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_UNIQUE


class AsyncHttpRepo[C: BaseModel, R: BaseModel, U: BaseModel]:
    """HTTP error handling for repositories whose database operations are async."""

    def __init__(
        self,
        repo: Any,
        logger: Logger,
        exception_msgs: Callable[[type[Exception]], str] | None = None,
        default_message: str = "An unexpected error occurred.",
    ) -> None:
        self.repo = repo
        self.logger = logger
        self.exception_msgs = exception_msgs
        self.default_message = default_message

    def handle_exception(self, ex: Exception) -> Never:
        self.logger.exception(ex)
        message = self.exception_msgs(type(ex)) if self.exception_msgs else self.default_message
        if isinstance(ex, DoesNotExist):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(ex, IntegrityError):
            status_code = status.HTTP_409_CONFLICT
            if "unique" in str(ex).lower() or is_unique_violation(ex):
                message = "This item already exists."
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code, detail=ErrorResponse.respond(message=message, exception=str(ex)))

    async def create_one(self, data: C) -> R:
        try:
            return await self.repo.create(data)
        except Exception as ex:
            self.handle_exception(ex)

    async def get_one(self, item_id: int | str | UUID4, key: str | None = None) -> R:
        item = await self.repo.get_one(item_id, key)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ErrorResponse.respond(message="Not found."))
        return item

    async def update_one(self, data: U, item_id: int | str | UUID4) -> R:
        await self.get_one(item_id)
        try:
            return await self.repo.update(item_id, data)
        except Exception as ex:
            self.handle_exception(ex)

    async def patch_one(self, data: U, item_id: int | str | UUID4) -> R:
        await self.get_one(item_id)
        try:
            return await self.repo.patch(item_id, data.model_dump(exclude_unset=True, exclude_defaults=True))
        except Exception as ex:
            self.handle_exception(ex)

    async def delete_one(self, item_id: int | str | UUID4) -> R:
        try:
            item = await self.repo.delete(item_id)
            self.logger.info(f"Deleting item with id {item_id}")
            return item
        except Exception as ex:
            self.handle_exception(ex)
