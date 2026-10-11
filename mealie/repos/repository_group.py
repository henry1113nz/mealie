from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from slugify import slugify
from tortoise import Model
from tortoise.exceptions import IntegrityError
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.db.models import _legacy_groups
from mealie.db.models.group import Group, ReportEntryModel, ReportModel
from mealie.db.models.group.ai_providers import AIProvider, AIProviderHeaders, AIProviderParams, AIProviderSettings
from mealie.db.models.group.exports import GroupDataExportsModel
from mealie.db.models.group.preferences import GroupPreferencesModel
from mealie.db.models.users.users import User
from mealie.schema._mealie import MealieModel
from mealie.schema.group.ai_providers import AIProviderSettingsOut
from mealie.schema.group.group_preferences import ReadGroupPreferences
from mealie.schema.reports.reports import ReportEntryOut
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.user.user import GroupInDB

from . import _users_coexistence as bridge
from .repository_users import AsyncUserRepository, LegacySession


class AsyncGroupRepository[Schema: MealieModel, DBModel: Model](AsyncUserRepository[Schema, DBModel]):
    """Tortoise persistence with explicit hydration of the unchanged group schemas."""

    async def _query(self) -> QuerySet[DBModel]:
        query = self.model.all()
        if self.group_id:
            if self.model is AIProvider:
                query = query.filter(settings__group_id=self.group_id)
            elif self.model is ReportEntryModel:
                query = query.filter(report__group_id=self.group_id)
            else:
                query = query.filter(group_id=self.group_id)
        return query

    async def _query_identifiers(self, pagination: PaginationQuery) -> list[Any]:
        legacy_model = getattr(_legacy_groups, self.model.__name__)
        return await bridge.query_model_ids(legacy_model, self.group_id, pagination)

    async def _serialize(self, entry: Model, schema: type[MealieModel] | None = None) -> Any:
        data = {key: getattr(entry, key) for key in entry._meta.db_fields}
        target = schema or self.schema
        if isinstance(entry, Group):
            preferences = await GroupPreferencesModel.filter(group_id=entry.id).first()
            settings = await AIProviderSettings.filter(group_id=entry.id).first()
            data.update(
                preferences=await self._serialize(preferences, ReadGroupPreferences) if preferences else None,
                ai_provider_settings=await self._serialize(settings, AIProviderSettingsOut) if settings else None,
            )
            if "households" in target.model_fields:
                data["households"] = await bridge.execute(
                    "SELECT id, name FROM households WHERE group_id = ?", [entry.id]
                )
            if "users" in target.model_fields:
                data["users"] = await User.filter(group_id=entry.id).values(
                    "id", "group_id", "household_id", "username", "full_name"
                )
            if "categories" in target.model_fields:
                data["categories"] = await bridge.execute(
                    "SELECT categories.* FROM categories JOIN group_to_categories "
                    "ON categories.id = group_to_categories.category_id WHERE group_to_categories.group_id = ?",
                    [entry.id],
                )
            if "webhooks" in target.model_fields:
                data["webhooks"] = await bridge.execute("SELECT * FROM webhook_urls WHERE group_id = ?", [entry.id])
        elif isinstance(entry, AIProviderSettings):
            data["providers"] = await AIProvider.filter(settings_id=entry.id).values("id", "name")
        elif isinstance(entry, AIProvider):
            data["request_headers"] = {
                row.key_name: row.value for row in await AIProviderHeaders.filter(provider_id=entry.id)
            }
            data["request_params"] = {
                row.key_name: row.value for row in await AIProviderParams.filter(provider_id=entry.id)
            }
        elif isinstance(entry, ReportModel) and "entries" in target.model_fields:
            data["entries"] = [
                await self._serialize(row, ReportEntryOut) for row in await ReportEntryModel.filter(report_id=entry.id)
            ]
        return target.model_validate(data)

    async def _prepare(self, data: dict[str, Any], *, creating: bool, entry: DBModel | None = None) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in self.model._meta.db_fields}
        # As with auto_init, creation can preserve a supplied UUID, while updates
        # never overwrite an existing primary key.
        if not creating or values.get("id") is None:
            values.pop("id", None)
        if self.model is GroupDataExportsModel and isinstance(values.get("expires"), datetime):
            values["expires"] = values["expires"].isoformat()
        if self.model is AIProviderSettings and entry is not None:
            for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
                if (
                    values.get(field) is not None
                    and not await AIProvider.filter(id=values[field], settings_id=entry.pk).exists()
                ):
                    raise ValueError("Provider does not belong to these group settings")
        return values

    async def delete(self, value: Any, match_key: str | None = None) -> Schema:
        async with in_transaction("default"):
            entry = await self._query_one(value, match_key)
            if isinstance(entry, ReportModel):
                result = await self._serialize(entry)
                await ReportEntryModel.filter(report_id=entry.id).delete()
                await entry.delete()
                await self._after_write(entry)
                return result
            return await super().delete(value, match_key)


class RepositoryGroup(AsyncGroupRepository[GroupInDB, Group]):
    def __init__(
        self, session: LegacySession, primary_key: str, sql_model: type[Group], schema: type[GroupInDB]
    ) -> None:
        super().__init__(session, primary_key, sql_model, schema, group_id=None)

    async def create(self, data: BaseModel | dict[str, Any]) -> GroupInDB:
        values = data.copy() if isinstance(data, dict) else data.model_dump()
        original_name = values["name"]
        for attempt in range(10):
            values["name"] = f"{original_name} ({attempt})" if attempt else original_name
            values["slug"] = slugify(values["name"])
            try:
                return await super().create(values)
            except IntegrityError:
                if attempt == 9:
                    raise
        raise RuntimeError("Unreachable group creation attempt")

    async def create_many(self, data: Iterable[GroupInDB | dict[str, Any]]) -> list[GroupInDB]:
        async with in_transaction("default"):
            return [await self.create(group) for group in data]

    async def update(self, match_value: Any, new_data: BaseModel | dict[str, Any]) -> GroupInDB:
        values = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        values["slug"] = slugify(values["name"])
        async with in_transaction("default"):
            group = await self._query_one(match_value)
            if "categories" in values:
                await self._replace_categories(group.id, values["categories"] or [])
            return await super().update(match_value, values)

    async def _replace_categories(self, group_id: UUID, categories: list[dict[str, Any]]) -> None:
        # Categories remain in C6. Execute their join-table mutation through the
        # owning Tortoise transaction and reject cross-group reassignment.
        for category in categories:
            existing = await bridge.related_record("categories", "id", category["id"], group_id=group_id)
            if not existing:
                raise ValueError("Category does not belong to this group")
        await bridge.execute("DELETE FROM group_to_categories WHERE group_id = ?", [group_id])
        for category in categories:
            await bridge.execute(
                "INSERT INTO group_to_categories (group_id, category_id) VALUES (?, ?)",
                [group_id, category["id"]],
            )

    async def get_by_name(self, name: str) -> GroupInDB | None:
        return await self.get_one(name, key="name")

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> GroupInDB | None:
        if isinstance(slug_or_id, str):
            try:
                slug_or_id = UUID(slug_or_id)
            except ValueError:
                pass
        return await self.get_one(slug_or_id, key="id" if isinstance(slug_or_id, UUID) else "slug")
