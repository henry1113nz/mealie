"""Async persistence and explicit hydration for recipe-domain resources."""

from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from slugify import slugify
from tortoise import Model, fields
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.db.models import _legacy_recipe
from mealie.db.models.household.household import Household
from mealie.db.models.recipe.api_extras import IngredientFoodExtras
from mealie.db.models.recipe.category import Category
from mealie.db.models.recipe.comment import RecipeComment
from mealie.db.models.recipe.ingredient import (
    IngredientFoodAliasModel,
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    IngredientUnitAliasModel,
    IngredientUnitModel,
)
from mealie.db.models.recipe.labels import MultiPurposeLabel
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.recipe_timeline import RecipeTimelineEvent
from mealie.db.models.recipe.shared import RecipeShareTokenModel
from mealie.db.models.recipe.tag import Tag
from mealie.db.models.recipe.tool import Tool
from mealie.db.models.users import User
from mealie.schema._mealie import MealieModel
from mealie.schema.response.pagination import PaginationBase, PaginationQuery

from ._recipe_query import query_identifiers
from .repository_users import AsyncUserRepository


def model_data(entry: Model) -> dict[str, Any]:
    return {key: getattr(entry, key) for key in entry._meta.db_fields}


async def hydrate_recipe_entity(entry: Model, *, shallow: bool = False) -> dict[str, Any]:
    data = model_data(entry)
    if isinstance(entry, IngredientFoodModel):
        if shallow:
            return data
        label = await MultiPurposeLabel.get_or_none(id=entry.label_id) if entry.label_id else None
        data["label"] = model_data(label) if label else None
        data["aliases"] = await IngredientFoodAliasModel.filter(food_id=entry.id).values()
        data["extras"] = {
            row.key_name: row.value for row in await IngredientFoodExtras.filter(ingredient_food_id=entry.id)
        }
        data["households_with_ingredient_food"] = await entry.households_with_ingredient_food.all().values_list(
            "slug", flat=True
        )
        data["substitutions"] = []
        for row in await IngredientFoodSubstitutionModel.filter(food_id=entry.id).order_by("position"):
            substitution = model_data(row)
            food = await IngredientFoodModel.get_or_none(id=row.substitute_food_id) if row.substitute_food_id else None
            substitution["substitute_food"] = model_data(food) if food else None
            data["substitutions"].append(substitution)
    elif isinstance(entry, IngredientUnitModel):
        data["aliases"] = await IngredientUnitAliasModel.filter(unit_id=entry.id).values()
    elif isinstance(entry, Tool):
        data["households_with_tool"] = await entry.households_with_tool.all().values_list("slug", flat=True)
    elif isinstance(entry, (Category, Tag)):
        data["recipe_count"] = await entry.recipes.all().count()
    elif isinstance(entry, (RecipeComment, RecipeTimelineEvent)):
        user = await User.get(id=entry.user_id)
        data["user"] = model_data(user)
        recipe = await RecipeModel.get(id=entry.recipe_id)
        owner = await User.get_or_none(id=recipe.user_id) if recipe.user_id else None
        data.update(group_id=recipe.group_id, household_id=owner.household_id if owner else None)
    elif isinstance(entry, RecipeShareTokenModel):
        from ._recipe_persistence import recipe_data

        data["recipe"] = await recipe_data(await RecipeModel.get(id=entry.recipe_id))
    return data


async def resolve_substitutions(
    group_id: UUID | None, substitutions: list[dict[str, Any]] | None, exclude_food_id: UUID | None = None
) -> list[tuple[UUID | None, str | None]]:
    if not substitutions or not group_id:
        return []
    requested: set[UUID] = set()
    for row in substitutions:
        if row.get("substitute_food_id"):
            try:
                requested.add(UUID(str(row["substitute_food_id"])))
            except ValueError:
                continue
    allowed = set(
        await IngredientFoodModel.filter(group_id=group_id, id__in=list(requested)).values_list("id", flat=True)
    )
    seen: set[UUID] = set()
    resolved: list[tuple[UUID | None, str | None]] = []
    for row in substitutions:
        raw_id = row.get("substitute_food_id")
        note = (row.get("note") or "").strip() or None
        if raw_id is None:
            if note:
                resolved.append((None, note))
            continue
        try:
            food_id = UUID(str(raw_id))
        except ValueError:
            continue
        if food_id not in allowed or food_id == exclude_food_id or food_id in seen:
            continue
        seen.add(food_id)
        resolved.append((food_id, note))
    return resolved


class AsyncRecipeRepository[Schema: MealieModel, DBModel: Model](AsyncUserRepository[Schema, DBModel]):
    async def _query(self) -> QuerySet[DBModel]:
        query = self.model.all()
        if self.group_id:
            if self.model in (RecipeComment, RecipeTimelineEvent):
                query = query.filter(recipe__group_id=self.group_id)
            else:
                query = query.filter(group_id=self.group_id)
        return query

    async def _serialize(self, entry: Model, schema: type[MealieModel] | None = None) -> Any:
        target = schema or self.schema
        data = await hydrate_recipe_entity(entry)
        if isinstance(entry, (Category, Tag, Tool)) and "recipes" in target.model_fields:
            from ._recipe_persistence import recipe_data

            data["recipes"] = [await recipe_data(recipe, summary=True) for recipe in await entry.recipes.all()]
        return target.model_validate(data)

    async def _query_identifiers(self, pagination: PaginationQuery) -> list[Any]:
        return await query_identifiers(getattr(_legacy_recipe, self.model.__name__), pagination, group_id=self.group_id)

    async def page_all(
        self, pagination: PaginationQuery, override: type[MealieModel] | None = None, search: str | None = None
    ) -> PaginationBase[Schema]:
        paging = pagination.model_copy()
        try:
            identifiers = await query_identifiers(
                getattr(_legacy_recipe, self.model.__name__),
                paging,
                group_id=self.group_id,
                search=search,
                schema=override or self.schema,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        count = len(identifiers)
        if paging.per_page == -1:
            paging.per_page = count
        pages = ceil(count / paging.per_page) if paging.per_page else 0
        if paging.page == -1:
            paging.page = pages
        paging.page = max(1, paging.page)
        start = (paging.page - 1) * paging.per_page
        identifiers = identifiers[start : start + paging.per_page]
        entries = {str(entry.pk): entry for entry in await (await self._query()).filter(pk__in=identifiers)}
        items = [
            await self._serialize(
                entries[str(UUID(str(key))) if isinstance(self.model._meta.pk, fields.UUIDField) else str(key)],
                override,
            )
            for key in identifiers
        ]
        return PaginationBase(page=paging.page, per_page=paging.per_page, total=count, total_pages=pages, items=items)

    async def _prepare(self, data: dict[str, Any], *, creating: bool, entry: DBModel | None = None) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in self.model._meta.db_fields}
        if not creating or values.get("id") is None:
            values.pop("id", None)
        if self.model in (Category, Tag, Tool) and "name" in values:
            values["slug"] = slugify(values["name"])
            if self.model in (Category, Tag):
                values["name"] = values["name"].strip()
                if not values["name"]:
                    raise ValueError("Organizer name must not be empty")
        if self.model is IngredientFoodModel and data.get("label") is not None:
            values["label_id"] = data["label"].get("id")
        if self.model is RecipeTimelineEvent:
            values["timestamp"] = data.get("timestamp") or datetime.now(UTC)
        if self.model is RecipeComment and not creating:
            return {"text": values["text"]} if "text" in values else {}
        return values

    async def _nested(self, entry: DBModel, data: dict[str, Any]) -> None:
        # These collections were constructor defaults on every legacy write.
        # patch() supplies the existing schema first, retaining omitted values.
        if isinstance(entry, IngredientFoodModel):
            data = {"extras": {}, "substitutions": [], "households_with_ingredient_food": []} | data
        elif isinstance(entry, Tool):
            data = {"households_with_tool": []} | data
        if isinstance(entry, (IngredientFoodModel, IngredientUnitModel)):
            food = isinstance(entry, IngredientFoodModel)
            alias_model = IngredientFoodAliasModel if food else IngredientUnitAliasModel
            owner_key = "food_id" if food else "unit_id"
            if "aliases" in data:
                await alias_model.filter(**{owner_key: entry.id}).delete()
                for alias in data["aliases"] or []:
                    await alias_model.create(**{owner_key: entry.id, "name": alias["name"]})
            if food:
                if "extras" in data:
                    await IngredientFoodExtras.filter(ingredient_food_id=entry.id).delete()
                    for key, value in (data["extras"] or {}).items():
                        await IngredientFoodExtras.create(ingredient_food_id=entry.id, key_name=key, value=value)
                if "substitutions" in data:
                    resolved = await resolve_substitutions(entry.group_id, data["substitutions"], entry.id)
                    current = await IngredientFoodSubstitutionModel.filter(food_id=entry.id).order_by("position")
                    by_food = {row.substitute_food_id: row for row in current if row.substitute_food_id}
                    notes = [row for row in current if row.substitute_food_id is None]
                    retained = []
                    for position, (food_id, note) in enumerate(resolved):
                        row = by_food.get(food_id) if food_id else (notes.pop(0) if notes else None)
                        if row:
                            row.note, row.position = note, position
                            await row.save(update_fields=["note", "position", "update_at"])
                        else:
                            row = await IngredientFoodSubstitutionModel.create(
                                food_id=entry.id, substitute_food_id=food_id, note=note, position=position
                            )
                        retained.append(row.id)
                    await IngredientFoodSubstitutionModel.filter(food_id=entry.id).exclude(id__in=retained).delete()
        relation_name = (
            "households_with_ingredient_food"
            if isinstance(entry, IngredientFoodModel)
            else "households_with_tool"
            if isinstance(entry, Tool)
            else None
        )
        if relation_name and relation_name in data:
            relation = getattr(entry, relation_name)
            await relation.clear()
            households = await Household.filter(group_id=entry.group_id, slug__in=data[relation_name] or [])
            if households:
                await relation.add(*households)

    async def create(self, data: BaseModel | dict[str, Any]) -> Schema:
        values = data.copy() if isinstance(data, dict) else data.model_dump()
        async with in_transaction("default"):
            entry = await self.model.create(**await self._prepare(values, creating=True))
            await self._nested(entry, values)
            await self._after_write(entry)
            return await self._serialize(entry)

    async def update(self, match_value: Any, new_data: BaseModel | dict[str, Any]) -> Schema:
        values = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        async with in_transaction("default"):
            entry = await self._query_one(match_value)
            entry.update_from_dict(await self._prepare(values, creating=False, entry=entry))
            await entry.save()
            await self._nested(entry, values)
            await self._after_write(entry)
            return await self._serialize(entry)
