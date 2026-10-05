from fastapi import HTTPException, status
from pydantic import UUID4, BaseModel

from mealie.db.models.group.ai_providers import AIProvider, AIProviderSettings
from mealie.schema.group.ai_providers import AIProviderOut

from .repository_generic import GroupRepositoryGeneric


class GroupRepositoryAIProvider(GroupRepositoryGeneric[AIProviderOut, AIProvider]):
    async def create(self, data: BaseModel | dict) -> AIProviderOut:
        if isinstance(data, BaseModel):
            data = data.model_dump() | {"api_key": getattr(data, "api_key", None)}
        if not data.get("api_key"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="API key cannot be empty")
        if not data.get("settings_id"):
            data["settings_id"] = (await AIProviderSettings.all().using_db(self.session).get(group_id=self.group_id)).id
        return await super().create(data)

    async def update(self, match_value: str | int | UUID4, new_data: BaseModel | dict) -> AIProviderOut:
        if isinstance(new_data, BaseModel):
            new_data = new_data.model_dump() | {"api_key": getattr(new_data, "api_key", None)}
        if not new_data.get("api_key"):
            existing = await self.get_one(match_value)
            if existing:
                new_data["api_key"] = existing.api_key
        return await super().update(match_value, new_data)

    async def delete(self, value, match_key: str | None = None) -> AIProviderOut:
        await self._query_one(value, match_key)
        for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
            await AIProviderSettings.filter(**{field: value}).using_db(self.session).update(**{field: None})
        return await super().delete(value, match_key)

    async def update_many(self, data):
        raise NotImplementedError
