"""Async repositories backed by Tortoise ORM.

These replace RepositoryGeneric one resource at a time. The method names and return types
match RepositoryGeneric so controllers only need to add ``await``.
"""

import random
import re
import types
import typing
from collections.abc import Iterable
from math import ceil
from typing import Any

from fastapi import HTTPException
from pydantic import UUID4, BaseModel
from tortoise.expressions import Q
from tortoise.models import Model
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.core.root_logger import get_logger
from mealie.db.tortoise.models import CASCADE_DELETE, NULLIFY_ON_DELETE, PROXIES
from mealie.schema._mealie import MealieModel
from mealie.schema.response.pagination import OrderDirection, PaginationBase, PaginationQuery
from mealie.services.query_filter.builder import NonFilterableValueError
from mealie.services.query_filter.tortoise_filter import TortoiseQueryFilter, order_term

_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def _to_snake(name: str) -> str:
    return _CAMEL.sub("_", name).lower()


def _nested_schema(annotation: Any) -> type[BaseModel] | None:
    """Finds the Pydantic model inside an annotation such as ``list[X] | None``."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if typing.get_origin(annotation) in (list, set, tuple, typing.Union, types.UnionType):
        for arg in typing.get_args(annotation):
            if found := _nested_schema(arg):
                return found
    return None


def relation_paths(model: type[Model], schema: type[BaseModel], prefix: str = "", depth: int = 0) -> list[str]:
    """Relations a schema reads from a model, as Tortoise prefetch paths.

    SQLAlchemy loaded relations lazily when a schema read them. Tortoise raises instead, so
    every relation the schema touches has to be fetched first.
    """
    if depth > 3:
        return []
    paths: list[str] = []
    for name, field in schema.model_fields.items():
        if name not in model._meta.fetch_fields:
            continue
        path = prefix + name
        paths.append(path)
        nested = _nested_schema(field.annotation)
        related = getattr(model._meta.fields_map[name], "related_model", None)
        if nested and related:
            paths.extend(relation_paths(related, nested, f"{path}__", depth + 1))
    return paths


def _writable_values(model: type[Model], data: dict[str, Any]) -> dict[str, Any]:
    """Keeps only keys that are columns of the model (including foreign key ids)."""
    meta = model._meta
    return {k: v for k, v in data.items() if k in meta.fields_map and k not in meta.fetch_fields}


async def write_children(obj: Model, data: dict[str, Any]) -> None:
    """Writes nested one-to-one and one-to-many data, as SQLAlchemy's auto_init did.

    One-to-one children are updated in place or created. One-to-many lists replace the stored
    children: rows whose id is in the list are updated, rows not in it are deleted, and items
    without a known id are created.
    """
    meta = obj._meta
    for name, value in data.items():
        if name in meta.backward_o2o_fields and isinstance(value, dict):
            field = meta.fields_map[name]
            child_model, fk = field.related_model, field.relation_field
            values = _writable_values(child_model, value)
            values.pop("id", None)
            values.pop(fk, None)
            existing = await child_model.filter(**{fk: obj.pk}).first()
            if existing:
                existing.update_from_dict(values)
                await existing.save()
            else:
                await child_model.create(**values, **{fk: obj.pk})
        elif name in meta.backward_fk_fields and isinstance(value, list):
            field = meta.fields_map[name]
            child_model, fk = field.related_model, field.relation_field
            stored = {child.pk: child for child in await child_model.filter(**{fk: obj.pk})}
            keep = set()
            for item in value:
                item_values = _writable_values(child_model, item if isinstance(item, dict) else dict(item))
                item_values.pop(fk, None)
                child = stored.get(item_values.get("id"))
                if child:
                    keep.add(child.pk)
                    child.update_from_dict(item_values)
                    await child.save()
                else:
                    if item_values.get("id") is None:
                        item_values.pop("id", None)
                    await child_model.create(**item_values, **{fk: obj.pk})
            for pk, child in stored.items():
                if pk not in keep:
                    await delete_with_relations(child)


async def delete_with_relations(obj: Model) -> None:
    """Deletes a row the way the SQLAlchemy relationships did: children marked for cascade are
    deleted (recursively), other children lose their foreign key, many-to-many links are removed.
    """
    meta = obj._meta
    name = type(obj).__name__
    for relation in CASCADE_DELETE.get(name, []):
        field = meta.fields_map[relation]
        for child in await field.related_model.filter(**{field.relation_field: obj.pk}):
            await delete_with_relations(child)
    for relation in NULLIFY_ON_DELETE.get(name, []):
        field = meta.fields_map[relation]
        await field.related_model.filter(**{field.relation_field: obj.pk}).update(**{field.relation_field: None})
    for relation in meta.m2m_fields:
        await getattr(obj, relation).clear()
    await obj.delete()


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
        # Several models reach their group or household through a relationship (an association
        # proxy in the SQLAlchemy models), e.g. a recipe's household is its user's household.
        # Never silently drop a scope that cannot be resolved.
        self._scope_paths: dict[str, str] = {}
        for key, value in (("group_id", group_id), ("household_id", household_id)):
            if not value:
                continue
            if key in model._meta.fields_map:
                self._scope_paths[key] = key
            elif key in PROXIES.get(model.__name__, {}):
                self._scope_paths[key] = PROXIES[model.__name__][key]
            else:
                raise ValueError(f"{model.__name__} has no {key}; it cannot be scoped by it")

    # ------------------------------------------------------------------ helpers

    def _scope(self, **kwargs: Any) -> dict[str, Any]:
        scope: dict[str, Any] = {}
        if self.group_id:
            scope[self._scope_paths["group_id"]] = self.group_id
        if self.household_id:
            scope[self._scope_paths["household_id"]] = self.household_id
        scope.update(kwargs)
        return scope

    def _query(self) -> QuerySet[TModel]:
        return self.model.filter(**self._scope())

    async def _to_schema(self, obj: TModel, schema: type[BaseModel] | None = None) -> Any:
        schema = schema or self.schema
        if paths := relation_paths(type(obj), schema):
            await obj.fetch_related(*paths)
        return schema.model_validate(obj)

    @staticmethod
    def _as_dict(data: BaseModel | dict) -> dict[str, Any]:
        return data if isinstance(data, dict) else data.model_dump()

    def _writable(self, data: dict[str, Any]) -> dict[str, Any]:
        return _writable_values(self.model, data)

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
        return await self._to_schema(obj, override_schema) if obj else None

    async def get_all(self, override: Any = None) -> list[Schema]:
        return [await self._to_schema(o, override) for o in await self._query()]

    async def multi_query(
        self,
        query_by: dict[str, Any],
        start: int = 0,
        limit: int | None = None,
        override_schema: Any = None,
        order_by: str | None = None,
    ) -> list[Schema]:
        # Same as RepositoryGeneric.multi_query: a None value filters for NULL, as filter_by did
        query = self._query().filter(**query_by)
        if order_by:
            query = query.order_by(f"-{order_by}")
        query = query.offset(start)
        if limit is not None:
            query = query.limit(limit)
        return [await self._to_schema(o, override_schema) for o in await query]

    async def count_all(self, match_key: str | None = None, match_value: Any = None) -> int:
        query = self._query()
        if match_key:
            query = query.filter(**{match_key: match_value})
        return await query.count()

    # ------------------------------------------------------------------ writes

    async def create(self, data: Schema | BaseModel | dict) -> Schema:
        raw = self._as_dict(data)
        values = self._writable(raw)
        # only real columns can be written; a proxied scope comes from the related row instead
        values.update({k: v for k, v in self._scope().items() if "__" not in k})
        async with in_transaction():
            obj = await self.model.create(**values)
            await write_children(obj, raw)
        return await self._to_schema(obj)

    async def create_many(self, data: Iterable[Schema | BaseModel | dict]) -> list[Schema]:
        return [await self.create(item) for item in data]

    async def update(self, match_value: Any, new_data: dict | BaseModel) -> Schema:
        obj = await self._query_one(match_value)
        raw = self._as_dict(new_data)
        values = self._writable(raw)
        # identity and ownership always come from the stored row
        for key in ("id", "group_id", "household_id"):
            values.pop(key, None)
        async with in_transaction():
            obj.update_from_dict(values)
            await obj.save()
            await write_children(obj, raw)
        return await self._to_schema(obj)

    async def patch(self, match_value: Any, new_data: dict | BaseModel) -> Schema:
        data = new_data if isinstance(new_data, dict) else new_data.model_dump(exclude_unset=True)
        return await self.update(match_value, data)

    async def delete(self, value: Any, match_key: str | None = None) -> Schema:
        obj = await self._query_one(value, match_key)
        result = await self._to_schema(obj)
        async with in_transaction():
            await delete_with_relations(obj)
        return result

    async def delete_many(self, values: Iterable[Any]) -> list[Schema]:
        objs = await self._query().filter(**{f"{self.primary_key}__in": list(values)})
        results = [await self._to_schema(o) for o in objs]
        async with in_transaction():
            for obj in objs:
                await delete_with_relations(obj)
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

    async def _apply_order(
        self, query: QuerySet[TModel], pagination: PaginationQuery
    ) -> tuple[QuerySet[TModel], list[Any] | None]:
        """Returns the ordered query, or for random ordering the shuffled ids to page through."""
        if not pagination.order_by:
            return query, None
        if pagination.order_by == "random":
            # shuffled outside the database so the order is stable for a given seed
            order = list(await query.values_list("id", flat=True))
            random.seed(pagination.pagination_seed)
            random.shuffle(order)
            return query, order

        terms: list[str] = []
        for part in pagination.order_by.split(","):
            part = part.strip()
            if ":" in part:
                name, direction_value = part.split(":")
                direction = OrderDirection(direction_value)
            else:
                name, direction = part, pagination.order_direction
            try:
                query, term = order_term(query, self.model, name, descending=direction is OrderDirection.desc)
            except NonFilterableValueError as e:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": {e}'
                ) from e
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f'Invalid order_by statement "{pagination.order_by}": "{part}" is invalid'
                ) from e
            terms.append(term)
        return query.order_by(*terms), None

    async def page_all(
        self, pagination: PaginationQuery, override: Any = None, search: str | None = None
    ) -> PaginationBase[Schema]:
        eff_schema = override or self.schema
        result = pagination.model_copy()

        query = self._query()
        if result.query_filter:
            try:
                query = TortoiseQueryFilter(result.query_filter).apply(query, self.model)
            except ValueError as e:
                self.logger.error(e)
                raise HTTPException(status_code=400, detail=str(e)) from e

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

        paths = relation_paths(self.model, eff_schema)
        query, random_order = await self._apply_order(query, result)
        offset = (result.page - 1) * result.per_page

        if random_order is not None:
            ids = random_order[offset : offset + limit if limit is not None else None]
            by_id = {o.id: o for o in await self.model.filter(id__in=ids).prefetch_related(*paths)}
            items = [by_id[i] for i in ids if i in by_id]
        else:
            if limit is not None:
                query = query.limit(limit)
            items = await query.offset(offset).prefetch_related(*paths)

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
