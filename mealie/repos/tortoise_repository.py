"""Async repositories backed by Tortoise ORM.

These replace RepositoryGeneric one resource at a time. The method names and return types
match RepositoryGeneric so controllers only need to add ``await``.
"""

import random
import re
from collections.abc import Iterable
from math import ceil
from typing import Any

from fastapi import HTTPException
from pydantic import UUID4, BaseModel
from tortoise.expressions import Q
from tortoise.models import Model
from tortoise.queryset import QuerySet

from mealie.core.root_logger import get_logger
from mealie.schema._mealie import MealieModel
from mealie.schema.response.pagination import OrderDirection, PaginationBase, PaginationQuery

_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def _to_snake(name: str) -> str:
    return _CAMEL.sub("_", name).lower()


class AsyncRepositoryGeneric[Schema: MealieModel, TModel: Model]:
    def __init__(
        self,
        model: type[TModel],
        schema: type[Schema],
        primary_key: str = "id",
        *,
        group_id: UUID4 | None = None,
        household_id: UUID4 | None = None,
    ) -> None:
        self.model = model
        self.schema = schema
        self.primary_key = primary_key
        self.group_id = group_id
        self.household_id = household_id
        self.logger = get_logger()

    # ------------------------------------------------------------------ helpers

    def _scope(self, **kwargs: Any) -> dict[str, Any]:
        scope: dict[str, Any] = {}
        if self.group_id:
            scope["group_id"] = self.group_id
        if self.household_id:
            scope["household_id"] = self.household_id
        scope.update(kwargs)
        return scope

    def _query(self) -> QuerySet[TModel]:
        return self.model.filter(**self._scope())

    def _field_name(self, name: str) -> str:
        """Maps an API field name (camelCase or snake_case) to a model field, or raises ValueError."""
        snake = _to_snake(name)
        if snake == "updated_at":
            snake = "update_at"
        if snake in self.model._meta.fields_map or snake in self.model._meta.fk_fields:
            return snake
        if snake.endswith("_id") and snake[:-3] in self.model._meta.fk_fields:
            return snake
        raise ValueError(name)

    def _to_schema(self, obj: TModel, schema: type[BaseModel] | None = None) -> Any:
        return (schema or self.schema).model_validate(obj)

    @staticmethod
    def _as_dict(data: BaseModel | dict) -> dict[str, Any]:
        return data if isinstance(data, dict) else data.model_dump()

    def _writable(self, data: dict[str, Any]) -> dict[str, Any]:
        """Keeps only keys that are model fields or foreign key ids."""
        fields = self.model._meta.fields_map
        return {k: v for k, v in data.items() if k in fields and k not in self.model._meta.fetch_fields}

    # ------------------------------------------------------------------ reads

    async def _query_one(self, match_value: Any, match_key: str | None = None) -> TModel:
        key = match_key or self.primary_key
        return await self._query().get(**{key: match_value})

    async def get_one(
        self, value: Any, key: str | None = None, any_case: bool = False, override_schema: Any = None
    ) -> Schema | None:
        key = key or self.primary_key
        query = self._query()
        if any_case and isinstance(value, str):
            query = query.filter(**{f"{key}__iexact": value})
        else:
            query = query.filter(**{key: value})
        obj = await query.first()
        return self._to_schema(obj, override_schema) if obj else None

    async def get_all(self, override: Any = None) -> list[Schema]:
        return [self._to_schema(o, override) for o in await self._query()]

    async def count_all(self, match_key: str | None = None, match_value: Any = None) -> int:
        query = self._query()
        if match_key:
            query = query.filter(**{match_key: match_value})
        return await query.count()

    # ------------------------------------------------------------------ writes

    async def create(self, data: Schema | BaseModel | dict) -> Schema:
        values = self._writable(self._as_dict(data))
        values.update(self._scope())
        obj = await self.model.create(**values)
        return self._to_schema(obj)

    async def create_many(self, data: Iterable[Schema | BaseModel | dict]) -> list[Schema]:
        return [await self.create(item) for item in data]

    async def update(self, match_value: Any, new_data: dict | BaseModel) -> Schema:
        obj = await self._query_one(match_value)
        values = self._writable(self._as_dict(new_data))
        # identity and ownership always come from the stored row
        for key in ("id", "group_id", "household_id"):
            values.pop(key, None)
        obj.update_from_dict(values)
        await obj.save()
        return self._to_schema(obj)

    async def patch(self, match_value: Any, new_data: dict | BaseModel) -> Schema:
        data = new_data if isinstance(new_data, dict) else new_data.model_dump(exclude_unset=True)
        return await self.update(match_value, data)

    async def delete(self, value: Any, match_key: str | None = None) -> Schema:
        obj = await self._query_one(value, match_key)
        result = self._to_schema(obj)
        await obj.delete()
        return result

    async def delete_many(self, values: Iterable[Any]) -> list[Schema]:
        objs = await self._query().filter(**{f"{self.primary_key}__in": list(values)})
        results = [self._to_schema(o) for o in objs]
        for obj in objs:
            await obj.delete()
        return results

    # ------------------------------------------------------------------ pagination

    def _apply_search(self, query: QuerySet[TModel], schema: type[MealieModel], search: str) -> QuerySet[TModel]:
        # Simplified: matches any searchable property containing the search text. The SQLAlchemy
        # version also normalizes accents and punctuation and ranks results.
        props = [p for p in getattr(schema, "_searchable_properties", []) if p in self.model._meta.fields_map]
        if not props:
            return query
        condition = Q()
        for prop in props:
            condition |= Q(**{f"{prop}__icontains": search})
        return query.filter(condition)

    async def _apply_order(self, query: QuerySet[TModel], pagination: PaginationQuery) -> QuerySet[TModel]:
        if not pagination.order_by:
            return query
        if pagination.order_by == "random":
            ids = await query.values_list("id", flat=True)
            order = list(ids)
            random.seed(pagination.pagination_seed)
            random.shuffle(order)
            # applied after fetching; see page_all
            self._random_order = order
            return query

        terms: list[str] = []
        for part in pagination.order_by.split(","):
            part = part.strip()
            if ":" in part:
                name, direction_value = part.split(":")
                direction = OrderDirection(direction_value)
            else:
                name, direction = part, pagination.order_direction
            try:
                field = self._field_name(name)
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": "{part}" is invalid'
                ) from e
            terms.append(field if direction is OrderDirection.asc else f"-{field}")
        return query.order_by(*terms)

    async def page_all(
        self, pagination: PaginationQuery, override: Any = None, search: str | None = None
    ) -> PaginationBase[Schema]:
        eff_schema = override or self.schema
        result = pagination.model_copy()

        if result.query_filter:
            # The query filter language is still built on SQLAlchemy expressions.
            raise HTTPException(status_code=400, detail="queryFilter is not supported on this endpoint yet")

        query = self._query()
        if search:
            query = self._apply_search(query, eff_schema, search)
        if not result.order_by and not search:
            result.order_by = "created_at"

        count = await query.count()
        limit: int | None = result.per_page
        if result.per_page == -1:
            result.per_page = count
            limit = None
        try:
            total_pages = ceil(count / result.per_page)
        except ZeroDivisionError:
            total_pages = 0
        if result.page == -1:
            result.page = total_pages
        if result.page < 1:
            result.page = 1

        self._random_order: list[Any] | None = None
        query = await self._apply_order(query, result)
        offset = (result.page - 1) * result.per_page

        if self._random_order is not None:
            ids = self._random_order[offset : offset + limit if limit is not None else None]
            by_id = {o.id: o for o in await self.model.filter(id__in=ids)}
            items = [by_id[i] for i in ids if i in by_id]
        else:
            if limit is not None:
                query = query.limit(limit)
            items = await query.offset(offset)

        return PaginationBase(
            page=result.page,
            per_page=result.per_page,
            total=count,
            total_pages=total_pages,
            items=[eff_schema.model_validate(o) for o in items],
        )


class AsyncGroupRepositoryGeneric[Schema: MealieModel, TModel: Model](AsyncRepositoryGeneric[Schema, TModel]):
    def __init__(self, model: type[TModel], schema: type[Schema], *, group_id: UUID4 | None) -> None:
        super().__init__(model, schema, group_id=group_id)
