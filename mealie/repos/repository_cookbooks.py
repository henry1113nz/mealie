import re
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from slugify import slugify
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from mealie.db.models.household.cookbook import CookBook
from mealie.repos.repository_household_base import AsyncHouseholdRepository
from mealie.schema.cookbook.cookbook import ReadCookBook, SaveCookBook
from mealie.schema.response.responses import ErrorResponse


class RepositoryCookbooks(AsyncHouseholdRepository[ReadCookBook, CookBook]):
    async def create(self, data: BaseModel | dict[str, Any]) -> ReadCookBook:
        if isinstance(data, dict):
            data = SaveCookBook(**data)
        values = data.model_dump()
        values["slug"] = slugify(values["name"])
        for attempt in range(10):
            try:
                return await super().create(values)
            except IntegrityError:
                if attempt == 9:
                    raise
                values["slug"] = slugify(f"{values['name']} ({attempt + 1})")
        raise RuntimeError("Unreachable cookbook creation attempt")

    async def create_many(self, data: Iterable[ReadCookBook | dict[str, Any]]) -> list[ReadCookBook]:
        async with in_transaction("default"):
            return [await self.create(entry) for entry in data]

    async def update(self, match_value: Any, data: BaseModel | dict[str, Any]) -> ReadCookBook:
        if isinstance(data, dict):
            data = SaveCookBook(**data)
        values = data.model_dump()
        new_slug = slugify(values["name"])
        if not (values.get("slug") and re.match(rf"^({new_slug})(-\d+)?$", values["slug"])):
            values["slug"] = new_slug
        for attempt in range(10):
            try:
                return await super().update(match_value, values)
            except IntegrityError:
                if attempt == 9:
                    raise
                values["slug"] = slugify(f"{values['name']} ({attempt + 1})")
        raise RuntimeError("Unreachable cookbook update attempt")

    async def update_many(self, data: Iterable[ReadCookBook | dict[str, Any]]) -> list[ReadCookBook]:
        async with in_transaction("default"):
            return [
                await self.update(entry.id if isinstance(entry, ReadCookBook) else entry["id"], entry) for entry in data
            ]

    async def patch(self, match_value: Any, data: BaseModel | dict[str, Any]) -> ReadCookBook:
        cookbook = await self.get_one(match_value)
        if not cookbook:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ErrorResponse.respond(message="Not found."))
        values = data if isinstance(data, dict) else data.model_dump()
        return await self.update(match_value, cookbook.model_dump() | values)
