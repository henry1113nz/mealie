from collections.abc import Iterable
from typing import cast
from uuid import UUID

from pydantic import UUID4, BaseModel
from slugify import slugify
from tortoise.exceptions import IntegrityError

from mealie.db.models.group import Group
from mealie.schema.user.user import GroupInDB

from .repository_generic import RepositoryGeneric


class RepositoryGroup(RepositoryGeneric[GroupInDB, Group]):
    async def create(self, data: BaseModel | dict) -> GroupInDB:
        if isinstance(data, BaseModel):
            data = data.model_dump()

        max_attempts = 10
        original_name = cast(str, data["name"])

        attempts = 0
        while True:
            try:
                data["slug"] = slugify(data["name"])
                return await super().create(data)
            except IntegrityError:
                attempts += 1
                if attempts >= max_attempts:
                    raise

                data["name"] = f"{original_name} ({attempts})"

    async def create_many(self, data: Iterable[BaseModel | dict]) -> list[GroupInDB]:
        # since create uses special logic for resolving slugs, we don't want to use the standard create_many method
        return [await self.create(new_group) for new_group in data]

    async def update(self, match_value: str | int | UUID4, new_data: BaseModel | dict) -> GroupInDB:
        if isinstance(new_data, BaseModel):
            new_data = new_data.model_dump()
        new_data["slug"] = slugify(new_data["name"])

        return await super().update(match_value, new_data)

    async def update_many(self, data: Iterable[BaseModel | dict]) -> list[GroupInDB]:
        # since update uses special logic for resolving slugs, we don't want to use the standard update_many method
        return [
            await self.update(group["id"] if isinstance(group, dict) else group.model_dump()["id"], group)
            for group in data
        ]

    async def get_by_name(self, name: str) -> GroupInDB | None:
        return await self.get_one(name, key="name")

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> GroupInDB | None:
        if isinstance(slug_or_id, str):
            try:
                slug_or_id = UUID(slug_or_id)
            except ValueError:
                pass

        if isinstance(slug_or_id, UUID):
            return await self.get_one(slug_or_id)
        else:
            return await self.get_one(slug_or_id, key="slug")
