from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from tortoise.transactions import in_transaction

from mealie.db.models.group.ai_providers import AIProvider, AIProviderHeaders, AIProviderParams, AIProviderSettings
from mealie.schema.group.ai_providers import AIProviderCreate, AIProviderOut

from .repository_group import AsyncGroupRepository


class GroupRepositoryAIProvider(AsyncGroupRepository[AIProviderOut, AIProvider]):
    @staticmethod
    def _values(data: BaseModel | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            return data.copy()
        values = data.model_dump()
        if isinstance(data, AIProviderCreate):
            # The unchanged schema intentionally excludes secrets from model_dump.
            values["api_key"] = data.api_key
        return values

    async def _replace_parameters(self, provider_id: Any, values: dict[str, Any]) -> None:
        for field, model in (("request_headers", AIProviderHeaders), ("request_params", AIProviderParams)):
            if field not in values:
                continue
            await model.filter(provider_id=provider_id).delete()
            for key, value in (values[field] or {}).items():
                await model.create(provider_id=provider_id, key_name=key, value=value)

    async def create(self, data: BaseModel | dict[str, Any]) -> AIProviderOut:
        values = self._values(data)
        if not values.get("api_key"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="API key cannot be empty")
        async with in_transaction("default"):
            settings = AIProviderSettings.all()
            if self.group_id:
                settings = settings.filter(group_id=self.group_id)
            if values.get("settings_id"):
                settings = settings.filter(id=values["settings_id"])
            owner = await settings.get()
            values["settings_id"] = owner.id
            entry = await self.model.create(**await self._prepare(values, creating=True))
            await self._replace_parameters(entry.id, values)
            await self._after_write(entry)
            return await self._serialize(entry)

    async def update(self, match_value: Any, new_data: BaseModel | dict[str, Any]) -> AIProviderOut:
        values = self._values(new_data)
        async with in_transaction("default"):
            entry = await self._query_one(match_value)
            if values.get("settings_id") and str(values["settings_id"]) != str(entry.settings_id):
                raise ValueError("Provider cannot be reassigned to different group settings")
            if not values.get("api_key"):
                values["api_key"] = entry.api_key
            entry.update_from_dict(await self._prepare(values, creating=False, entry=entry))
            await entry.save()
            await self._replace_parameters(entry.id, values)
            await self._after_write(entry)
            return await self._serialize(entry)

    async def delete(self, value: Any, match_key: str | None = None) -> AIProviderOut:
        async with in_transaction("default"):
            # Fetch within this repository's scope before touching references.
            entry = await self._query_one(value, match_key)
            result = await self._serialize(entry)
            for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
                await AIProviderSettings.filter(**{field: entry.id}).update(
                    **{field: None, "update_at": datetime.now(UTC)}
                )
            await AIProviderHeaders.filter(provider_id=entry.id).delete()
            await AIProviderParams.filter(provider_id=entry.id).delete()
            await entry.delete()
            await self._after_write(entry)
            return result

    async def update_many(self, data: Iterable[AIProviderOut | dict[str, Any]]) -> list[AIProviderOut]:
        raise NotImplementedError
