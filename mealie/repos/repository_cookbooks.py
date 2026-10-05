import re
from collections.abc import Iterable

from fastapi import HTTPException, status
from pydantic import UUID4, BaseModel
from slugify import slugify
from tortoise.exceptions import IntegrityError

from mealie.db.models.household.cookbook import CookBook
from mealie.repos.repository_generic import HouseholdRepositoryGeneric
from mealie.schema.cookbook.cookbook import ReadCookBook, SaveCookBook
from mealie.schema.response.responses import ErrorResponse


class RepositoryCookbooks(HouseholdRepositoryGeneric[ReadCookBook, CookBook]):
    async def create(self, data: BaseModel | dict) -> ReadCookBook:
        if not isinstance(data, SaveCookBook):
            data = SaveCookBook.model_validate(data if isinstance(data, dict) else data.model_dump())
        data.slug = slugify(data.name)

        max_retries = 10
        for i in range(max_retries):
            try:
                return await super().create(data)
            except IntegrityError:
                data.slug = slugify(f"{data.name} ({i + 1})")

        raise  # raise the last IntegrityError

    async def create_many(self, data: Iterable[BaseModel | dict]) -> list[ReadCookBook]:
        return [await self.create(entry) for entry in data]

    async def update(self, match_value: str | int | UUID4, data: BaseModel | dict) -> ReadCookBook:
        if not isinstance(data, SaveCookBook):
            existing = await self._query_one(match_value)
            values = data if isinstance(data, dict) else data.model_dump()
            data = SaveCookBook.model_validate(
                {"group_id": existing.group_id, "household_id": existing.household_id} | values
            )

        new_slug = slugify(data.name)
        if not (data.slug and re.match(rf"^({new_slug})(-\d+)?$", data.slug)):
            data.slug = new_slug

        max_retries = 10
        for i in range(max_retries):
            try:
                return await super().update(match_value, data)
            except IntegrityError:
                data.slug = slugify(f"{data.name} ({i + 1})")

        raise  # raise the last IntegrityError

    async def update_many(self, data: Iterable[BaseModel | dict]) -> list[ReadCookBook]:
        return [
            await self.update(entry["id"] if isinstance(entry, dict) else entry.model_dump()["id"], entry)
            for entry in data
        ]

    async def patch(self, match_value: str | int | UUID4, data: BaseModel | dict) -> ReadCookBook:
        cookbook = await self.get_one(match_value)
        if not cookbook:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.respond(message="Not found."),
            )
        cookbook_data = cookbook.model_dump()

        if not isinstance(data, dict):
            data = data.model_dump()
        return await self.update(match_value, cookbook_data | data)
