"""Async repository primitives for the incremental Tortoise migration.

The existing SQLAlchemy repositories remain the application path until their
callers are migrated.  This module is deliberately independent so new async
callers can adopt the same CRUD, scoping, transaction and serialization rules.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
from math import ceil
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from tortoise import Model, connections
from tortoise.transactions import in_transaction

from mealie.schema.response.pagination import (
    OrderByNullPosition,
    OrderDirection,
    PaginationBase,
    PaginationQuery,
)
from mealie.services.query_filter.tortoise import TortoiseFilterCompiler, validate_order_path

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

    async def page_all(
        self,
        pagination: PaginationQuery,
        *,
        related_fields: Sequence[str] = (),
    ) -> PaginationBase[SchemaT]:
        """Apply Mealie filter, ordering and pagination semantics asynchronously."""
        request = pagination.model_copy()
        query = self._query()
        if request.query_filter:
            try:
                query = query.filter(TortoiseFilterCompiler.compile(request.query_filter, self.model))
            except ValueError as error:
                from fastapi import HTTPException

                raise HTTPException(status_code=400, detail=str(error)) from error

        # Related predicates compile as primary-key subqueries, keeping this
        # count at one row per root record.
        total = await query.count()
        if request.per_page == -1:
            request.per_page = total
            limit: int | None = None
        else:
            limit = request.per_page
        total_pages = ceil(total / request.per_page) if request.per_page else 0
        if request.page == -1:
            request.page = total_pages
        request.page = max(request.page, 1)

        rows = await query
        if request.order_by == "random":
            ids = [getattr(row, self.primary_key) for row in rows]
            ordering = list(range(len(ids)))
            random.seed(request.pagination_seed)
            random.shuffle(ordering)
            rank = dict(zip(ids, ordering, strict=True))
            rows.sort(key=lambda row: rank[getattr(row, self.primary_key)])
        else:
            order_by = request.order_by or ("created_at" if hasattr(self.model, "created_at") else None)
            if order_by:
                terms: list[tuple[str, OrderDirection, bool, bool]] = []
                for term in order_by.split(","):
                    term = term.strip()
                    if ":" in term:
                        path, direction_text = term.rsplit(":", maxsplit=1)
                        try:
                            direction = OrderDirection(direction_text)
                        except ValueError as error:
                            from fastapi import HTTPException

                            raise HTTPException(
                                status_code=400,
                                detail=f'Invalid order_by statement "{order_by}": "{term}" is invalid',
                            ) from error
                    else:
                        path, direction = term, request.order_direction
                    try:
                        tortoise_path, is_related, to_many = validate_order_path(self.model, path)
                    except ValueError as error:
                        from fastapi import HTTPException

                        raise HTTPException(
                            status_code=400,
                            detail=f'Invalid order_by statement "{order_by}": "{term}" is invalid',
                        ) from error
                    terms.append((tortoise_path, direction, is_related, to_many))

                # Apply stable sorts from least to most significant. Related
                # values are reduced to MIN (ascending) or MAX (descending),
                # matching the legacy correlated aggregate.
                for path, direction, is_related, to_many in reversed(terms):
                    values_by_id: dict[Any, Any] = {}
                    for row in rows:
                        row_id = getattr(row, self.primary_key)
                        if is_related:
                            values = await self.model.filter(**{self.primary_key: row_id}).values_list(path, flat=True)
                            values = [value for value in values if value is not None]
                            if values:
                                if to_many:
                                    values_by_id[row_id] = (
                                        min(values) if direction is OrderDirection.asc else max(values)
                                    )
                                else:
                                    values_by_id[row_id] = values[0]
                            else:
                                values_by_id[row_id] = None
                        else:
                            values_by_id[row_id] = self._scalar_path(row, path)

                    non_null = [row for row in rows if values_by_id[getattr(row, self.primary_key)] is not None]
                    null_rows = [row for row in rows if values_by_id[getattr(row, self.primary_key)] is None]
                    non_null.sort(
                        key=lambda row: self._normalize_sort_value(values_by_id[getattr(row, self.primary_key)]),
                        reverse=direction is OrderDirection.desc,
                    )
                    if request.order_by_null_position is None:
                        dialect = connections.get("default").capabilities.dialect
                        nulls_first = (dialect == "sqlite" and direction is OrderDirection.asc) or (
                            dialect == "postgres" and direction is OrderDirection.desc
                        )
                    else:
                        nulls_first = request.order_by_null_position is OrderByNullPosition.first
                    rows = null_rows + non_null if nulls_first else non_null + null_rows

        if limit is not None:
            start = (request.page - 1) * request.per_page
            rows = rows[start : start + limit]
        relations = tuple(dict.fromkeys((*self.related_fields, *related_fields)))
        return PaginationBase(
            page=request.page,
            per_page=request.per_page,
            total=total,
            total_pages=total_pages,
            items=[await self._serialize(row, related_fields=relations) for row in rows],
        )

    @staticmethod
    def _scalar_path(instance: Model, path: str) -> Any:
        value: Any = instance
        for part in path.split("__"):
            value = getattr(value, part)
        return value

    @staticmethod
    def _normalize_sort_value(value: Any) -> Any:
        return value.casefold() if isinstance(value, str) else value


class GroupAsyncRepository(AsyncRepository[SchemaT, ModelT]):
    """Repository scoped to a group; ``None`` explicitly means unscoped."""


class HouseholdAsyncRepository(AsyncRepository[SchemaT, ModelT]):
    """Repository scoped to a household and, optionally, its group."""
