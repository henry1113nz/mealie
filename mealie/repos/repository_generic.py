from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from math import ceil
from typing import Any, cast

from fastapi import HTTPException
from pydantic import UUID4, BaseModel
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.expressions import Case, When
from tortoise.fields.relational import RelationalField
from tortoise.functions import Lower
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.core.root_logger import get_logger
from mealie.db.models._model_base import TortoiseModel
from mealie.schema._mealie import MealieModel
from mealie.schema.response.pagination import (
    OrderByNullPosition,
    OrderDirection,
    PaginationBase,
    PaginationQuery,
    RequestQuery,
)
from mealie.schema.response.query_search import SearchFilter
from mealie.services.query_filter.builder import QueryFilterBuilder
from mealie.services.query_filter.expressions import RelatedOrder

from ._utils import NotSet


class RepositoryGeneric[Schema: MealieModel, DBModel: TortoiseModel]:
    """Async, tenant-scoped access to native Tortoise models."""

    _group_id: UUID4 | None = None
    _household_id: UUID4 | None = None

    def __init__(
        self, session: BaseDBAsyncClient, primary_key: str, sql_model: type[DBModel], schema: type[Schema]
    ) -> None:
        self.session = session
        self.primary_key = primary_key
        self.model = sql_model
        self.schema = schema
        self.logger = get_logger()

    @property
    def group_id(self) -> UUID4 | None:
        return self._group_id

    @property
    def household_id(self) -> UUID4 | None:
        return self._household_id

    @property
    def column_aliases(self) -> dict[str, str]:
        return {}

    def _random_seed(self) -> str:
        return str(datetime.now(tz=UTC))

    def _log_exception(self, error: Exception) -> None:
        self.logger.error(f"Error processing query for Repo model={self.model.__name__} schema={self.schema.__name__}")
        self.logger.error(error)

    def _query(self, override_schema=None, with_options=True) -> QuerySet[DBModel]:
        return self.model.all().using_db(self.session)

    def _field_path(self, key: str) -> str:
        current = self.model
        pending = deque(key.replace(".", "__").split("__"))
        path = []
        while pending:
            name = pending.popleft()
            if proxy := getattr(current, "__association_proxies__", {}).get(name):
                pending.extendleft(reversed(proxy))
                continue
            path.append(name)
            field = current._meta.fields_map.get(name)
            related = getattr(field, "related_model", None)
            if related is not None:
                current = related
        return "__".join(path)

    def _filter_builder(self, **kwargs) -> dict[str, Any]:
        filters = {}
        if self.group_id:
            filters["group_id"] = self.group_id
        if self.household_id:
            filters["household_id"] = self.household_id
        return {self._field_path(key): value for key, value in (filters | kwargs).items()}

    async def _to_schema(self, instance: DBModel, schema=None) -> Schema:
        return cast(Schema, await instance.to_schema(schema or self.schema))

    async def _to_schemas(self, instances: Iterable[DBModel], schema=None) -> list[Schema]:
        entries = list(instances)
        effective_schema = schema or self.schema
        paths = []
        for path in effective_schema.loader_options():
            current = self.model
            for part in path.split("__"):
                if part not in current._meta.fetch_fields:
                    break
                current = cast(RelationalField, current._meta.fields_map[part]).related_model
            else:
                paths.append(path)
        if entries and paths:
            await self.model.fetch_for_list(entries, *paths)
        return [await self._to_schema(instance, effective_schema) for instance in entries]

    async def get_all(
        self, limit: int | None = None, order_by: str | None = None, order_descending=True, override=None
    ) -> list[Schema]:
        pagination = PaginationQuery(
            per_page=limit or -1,
            order_by=order_by,
            order_direction=OrderDirection.desc if order_descending else OrderDirection.asc,
            page=1,
        )
        return (await self.page_all(pagination, override=override)).items

    async def multi_query(
        self, query_by: dict, start=0, limit=None, override_schema=None, order_by=None
    ) -> list[Schema]:
        query = self._query().filter(**self._filter_builder(**query_by)).offset(start)
        if limit is not None:
            query = query.limit(limit)
        if order_by:
            query = query.order_by("-" + self._field_path(order_by))
        return await self._to_schemas(await query, override_schema)

    async def _query_one(self, match_value: str | int | UUID4, match_key: str | None = None) -> DBModel:
        return await self._query().get(**self._filter_builder(**{match_key or self.primary_key: match_value}))

    async def get_one(self, value: str | int | UUID4, key=None, any_case=False, override_schema=None) -> Schema | None:
        key = self._field_path(key or self.primary_key)
        if any_case:
            key += "__iexact"
        result = await self._query().filter(**self._filter_builder(**{key: value})).first()
        return await self._to_schema(result, override_schema) if result is not None else None

    async def create(self, data: Schema | BaseModel | dict) -> Schema:
        values = data.copy() if isinstance(data, dict) else data.model_dump()
        async with in_transaction(self.session.connection_name) as connection:
            result = await self.model.create_from_data(values, using_db=connection)
            return await self._to_schema(result)

    async def create_many(self, data: Iterable[Schema | BaseModel | dict]) -> list[Schema]:
        async with in_transaction(self.session.connection_name) as connection:
            results = [
                await self.model.create_from_data(
                    item.copy() if isinstance(item, dict) else item.model_dump(), using_db=connection
                )
                for item in data
            ]
            return await self._to_schemas(results)

    async def update(self, match_value: str | int | UUID4, new_data: dict | BaseModel) -> Schema:
        values = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        async with in_transaction(self.session.connection_name) as connection:
            entry = (
                await self._query().using_db(connection).get(**self._filter_builder(**{self.primary_key: match_value}))
            )
            await entry.update_from_data(values, using_db=connection)
            return await self._to_schema(entry)

    async def update_many(self, data: Iterable[Schema | BaseModel | dict]) -> list[Schema]:
        values = {}
        for document in data:
            item = document if isinstance(document, dict) else document.model_dump()
            values[str(item["id"])] = item
        async with in_transaction(self.session.connection_name) as connection:
            entries = await self._query().using_db(connection).filter(id__in=list(values), **self._filter_builder())
            for entry in entries:
                await entry.update_from_data(values[str(entry.id)], using_db=connection)
            return await self._to_schemas(entries)

    async def patch(self, match_value: str | int | UUID4, new_data: dict | BaseModel) -> Schema:
        entry = await self._query_one(match_value)
        values = (await self._to_schema(entry)).model_dump()
        values.update(new_data if isinstance(new_data, dict) else new_data.model_dump())
        return await self.update(match_value, values)

    async def delete(self, value, match_key=None) -> Schema:
        entry = await self._query_one(value, match_key)
        result = await self._to_schema(entry)
        await entry.delete(using_db=self.session)
        return result

    async def delete_many(self, values: Iterable) -> list[Schema]:
        entries = await self._query().filter(id__in=list(values), **self._filter_builder())
        result = await self._to_schemas(entries)
        async with in_transaction(self.session.connection_name) as connection:
            for entry in entries:
                await entry.delete(using_db=connection)
        return result

    async def delete_all(self) -> None:
        await self._query().filter(**self._filter_builder()).delete()

    async def count_all(self, match_key=None, match_value=None) -> int:
        filters = {} if match_key is None or match_value is None else {match_key: match_value}
        return await self._query().filter(**self._filter_builder(**filters)).count()

    async def _count_attribute(self, attribute_name: str, attr_match=None, count=True, override_schema=None):
        field = self.model._meta.fields_map[attribute_name]
        path = attribute_name + "__id" if isinstance(field, RelationalField) else attribute_name
        lookup = path + "__isnull" if attr_match is None else path
        query = self._query().filter(**self._filter_builder(), **{lookup: True if attr_match is None else attr_match})
        if count:
            return await query.distinct().count()
        return await self._to_schemas(await query.distinct(), override_schema)

    async def page_all(
        self, pagination: PaginationQuery, override=None, *, search: str | None = None
    ) -> PaginationBase:
        pagination = pagination.model_copy()
        query = self._query().filter(**self._filter_builder())
        if search:
            query = self.add_search_to_query(query, override or self.schema, search)
        if not pagination.order_by and not search:
            pagination.order_by = "created_at"
        query, count, pages = await self.add_pagination_to_query(query, pagination)
        return PaginationBase(
            page=pagination.page,
            per_page=pagination.per_page,
            total=count,
            total_pages=pages,
            items=await self._to_schemas(await query, override),
        )

    async def add_pagination_to_query(self, query: QuerySet, pagination: PaginationQuery) -> tuple[QuerySet, int, int]:
        if pagination.query_filter:
            try:
                query = QueryFilterBuilder(pagination.query_filter).filter_query(query, self.model, self.column_aliases)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
        count = await query.distinct().count()
        limit = None if pagination.per_page == -1 else pagination.per_page
        if limit is None:
            pagination.per_page = count
        pages = ceil(count / pagination.per_page) if pagination.per_page else 0
        if pagination.page == -1:
            pagination.page = pages
        pagination.page = max(1, pagination.page)
        query = await self.add_order_by_to_query(query, pagination)
        if limit is not None:
            query = query.limit(limit)
        return query.offset((pagination.page - 1) * pagination.per_page), count, pages

    async def add_order_by_to_query(self, query: QuerySet, request_query: RequestQuery) -> QuerySet:
        if not request_query.order_by:
            return query
        if request_query.order_by == "random":
            ids = await query.values_list("id", flat=True)
            random.Random(request_query.pagination_seed).shuffle(ids)
            if ids:
                query = query.annotate(
                    _random_order=Case(
                        *[When(id=pk, then=cast(Any, index)) for index, pk in enumerate(ids)], default=cast(Any, 0)
                    )
                )
                return query.order_by("_random_order")
            return query
        # Search relevance remains the primary ordering; explicit pagination fields
        # break ties, matching the API's established search ranking.
        ordering = [("-" if direction.value == "DESC" else "") + name for name, direction in query._orderings]
        for index, value in enumerate(request_query.order_by.split(",")):
            try:
                field, separator, direction = value.strip().partition(":")
                order_direction = OrderDirection(direction) if separator else request_query.order_direction
                descending = order_direction is OrderDirection.desc
                path, field_type, related = QueryFilterBuilder.resolve_attribute(field, self.model)
                path = self.column_aliases.get(path, path)
                annotation = f"_order_{index}"
                expression: Any = Lower(path) if field_type.field_type is str else path
                if related:
                    expression = RelatedOrder(path, descending=descending, string=field_type.field_type is str)
                if not isinstance(expression, str):
                    query = query.annotate(**{annotation: expression})
                    path = annotation
                null_position = request_query.order_by_null_position
                if null_position:
                    null_annotation = f"_null_{index}"
                    query = query.annotate(
                        **{
                            null_annotation: Case(
                                When(**{path + "__isnull": True}, then=cast(Any, 0)), default=cast(Any, 1)
                            )
                        }
                    )
                    ordering.append(("-" if null_position is OrderByNullPosition.last else "") + null_annotation)
                ordering.append(("-" if descending else "") + path)
            except ValueError as error:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{request_query.order_by}": {error}'
                ) from error
        return query.order_by(*ordering)

    def add_search_to_query(self, query: QuerySet, schema: type[Schema], search: str) -> QuerySet:
        return SearchFilter(self.session, search, schema._normalize_search).filter_query_by_search(
            query, schema, self.model
        )


class GroupRepositoryGeneric[Schema: MealieModel, DBModel: TortoiseModel](RepositoryGeneric[Schema, DBModel]):
    def __init__(self, session, primary_key, sql_model, schema, *, group_id: UUID4 | None | NotSet) -> None:
        super().__init__(session, primary_key, sql_model, schema)
        if isinstance(group_id, NotSet):
            raise ValueError("group_id must be set")
        self._group_id = group_id or None


class HouseholdRepositoryGeneric[Schema: MealieModel, DBModel: TortoiseModel](RepositoryGeneric[Schema, DBModel]):
    def __init__(
        self,
        session,
        primary_key,
        sql_model,
        schema,
        *,
        group_id: UUID4 | None | NotSet,
        household_id: UUID4 | None | NotSet,
    ) -> None:
        super().__init__(session, primary_key, sql_model, schema)
        if isinstance(group_id, NotSet):
            raise ValueError("group_id must be set")
        if isinstance(household_id, NotSet):
            raise ValueError("household_id must be set")
        self._group_id = group_id or None
        self._household_id = household_id or None
