"""Async repository primitives for the incremental Tortoise migration.

The existing SQLAlchemy repositories remain the application path until their
callers are migrated.  This module is deliberately independent so new async
callers can adopt the same CRUD, scoping, transaction and serialization rules.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from tortoise import Model
from tortoise.transactions import in_transaction

SchemaT = TypeVar("SchemaT", bound=BaseModel)
ModelT = TypeVar("ModelT", bound=Model)


class AsyncRepository(Generic[SchemaT, ModelT]):
    """Async CRUD access with explicit tenant scoping and relation loading."""

    def __init__(
        self,
        model: type[ModelT],
        schema: type[SchemaT],
        *,
        primary_key: str = "id",
        group_id: Any | None = None,
        household_id: Any | None = None,
        related_fields: Sequence[str] = (),
    ) -> None:
        self.model = model
        self.schema = schema
        self.primary_key = primary_key
        self.group_id = group_id
        self.household_id = household_id
        self.related_fields = tuple(related_fields)

    def _filters(self, **filters: Any) -> dict[str, Any]:
        scoped = dict(filters)
        if self.group_id is not None and "group_id" in self.model._meta.fields_db_projection:
            scoped["group_id"] = self.group_id
        if self.household_id is not None and "household_id" in self.model._meta.fields_db_projection:
            scoped["household_id"] = self.household_id
        return scoped

    def _query(self, **filters: Any):
        query = self.model.filter(**self._filters(**filters))
        if self.related_fields:
            query = query.select_related(*self.related_fields)
        return query

    async def _serialize(self, instance: ModelT, *, related_fields: Sequence[str] = ()) -> SchemaT:
        relations = tuple(dict.fromkeys((*self.related_fields, *related_fields)))
        if relations:
            await instance.fetch_related(*relations)
        return self.schema.model_validate(instance, from_attributes=True)

    async def get_one(
        self,
        value: Any,
        *,
        key: str | None = None,
        related_fields: Sequence[str] = (),
    ) -> SchemaT | None:
        instance = await self._query(**{key or self.primary_key: value}).first()
        if instance is None:
            return None
        return await self._serialize(instance, related_fields=related_fields)

    async def get_all(self, *, related_fields: Sequence[str] = (), **filters: Any) -> list[SchemaT]:
        query = self._query(**filters)
        relations = tuple(dict.fromkeys((*self.related_fields, *related_fields)))
        if relations:
            query = query.select_related(*relations)
        instances = await query
        return [await self._serialize(instance) for instance in instances]

    @staticmethod
    def _data(data: SchemaT | BaseModel | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(data, Mapping):
            return dict(data)
        return data.model_dump(exclude_unset=True)

    async def create(self, data: SchemaT | BaseModel | Mapping[str, Any]) -> SchemaT:
        async with in_transaction() as connection:
            instance = await self.model.create(using_db=connection, **self._data(data))
        return await self._serialize(instance)

    async def create_many(self, data: Iterable[SchemaT | Mapping[str, Any]]) -> list[SchemaT]:
        rows = [self.model(**self._data(row)) for row in data]
        if not rows:
            return []
        async with in_transaction() as connection:
            await self.model.bulk_create(rows, using_db=connection)
        return [await self._serialize(row) for row in rows]

    async def update(self, value: Any, data: SchemaT | BaseModel | Mapping[str, Any]) -> SchemaT | None:
        changes = self._data(data)
        changes.pop(self.primary_key, None)
        async with in_transaction() as connection:
            instance = await self._query(**{self.primary_key: value}).using_db(connection).first()
            if instance is None:
                return None
            for field, field_value in changes.items():
                setattr(instance, field, field_value)
            await instance.save(using_db=connection, update_fields=list(changes))
        return await self._serialize(instance)

    async def delete(self, value: Any) -> SchemaT | None:
        async with in_transaction() as connection:
            instance = await self._query(**{self.primary_key: value}).using_db(connection).first()
            if instance is None:
                return None
            result = await self._serialize(instance)
            await instance.delete(using_db=connection)
        return result

    async def delete_many(self, values: Iterable[Any]) -> list[SchemaT]:
        keys = list(values)
        if not keys:
            return []
        async with in_transaction() as connection:
            instances = await self._query(**{f"{self.primary_key}__in": keys}).using_db(connection)
            results = [await self._serialize(instance) for instance in instances]
            for instance in instances:
                await instance.delete(using_db=connection)
        return results

    async def count(self, **filters: Any) -> int:
        return await self._query(**filters).count()


class GroupAsyncRepository(AsyncRepository[SchemaT, ModelT]):
    """Repository scoped to a group; ``None`` explicitly means unscoped."""


class HouseholdAsyncRepository(AsyncRepository[SchemaT, ModelT]):
    """Repository scoped to a household and, optionally, its group."""
