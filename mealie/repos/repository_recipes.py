from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from math import ceil
from typing import Any, Self
from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException
from pydantic import UUID4, BaseModel
from slugify import slugify
from tortoise import Model, connections
from tortoise.exceptions import IntegrityError
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.core.root_logger import get_logger
from mealie.db.models._legacy_household import HouseholdToRecipe
from mealie.db.models._legacy_recipe.category import Category as LegacyCategory
from mealie.db.models._legacy_recipe.ingredient import RecipeIngredientModel as LegacyIngredient
from mealie.db.models._legacy_recipe.ingredient import RecipeIngredientSubstitutionModel as LegacySubstitution
from mealie.db.models._legacy_recipe.recipe import RecipeModel as LegacyRecipe
from mealie.db.models._legacy_recipe.tag import Tag as LegacyTag
from mealie.db.models._legacy_recipe.tool import Tool as LegacyTool
from mealie.db.models._legacy_users import User, UserToRecipe
from mealie.db.models.household.household import Household
from mealie.db.models.recipe.category import Category
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.tag import Tag
from mealie.db.models.recipe.tool import Tool
from mealie.pkgs import cache
from mealie.schema._mealie import MealieModel, SearchType
from mealie.schema.cookbook.cookbook import ReadCookBook
from mealie.schema.recipe import Recipe
from mealie.schema.recipe.recipe import RecipePagination, RecipeSummary, create_recipe_slug
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.query_search import SearchFilter
from mealie.services.query_filter.builder import QueryFilterBuilder

from ._recipe_persistence import recipe_data, replace_recipe_children
from ._recipe_query import SearchSession, execute_select, query_identifiers
from ._recipe_suggestions import RecipeSuggestionMixin
from ._utils import NOT_SET, NotSet
from .repository_users import AsyncUserRepository, LegacySession


class RepositoryRecipes(RecipeSuggestionMixin, AsyncUserRepository[Recipe, RecipeModel]):
    user_id: UUID4 | None = None

    def __init__(
        self,
        session: LegacySession,
        primary_key: str,
        sql_model: type[RecipeModel],
        schema: type[Recipe],
        *,
        group_id: UUID | None | NotSet,
        household_id: UUID | None | NotSet,
    ) -> None:
        super().__init__(session, primary_key, sql_model, schema, group_id=group_id)
        if household_id is NOT_SET:
            raise ValueError("household_id must be set")
        self.household_id = UUID(str(household_id)) if household_id else None
        self.logger = get_logger()

    def _filter_builder(self, **kwargs: Any) -> dict[str, Any]:
        filters = dict(kwargs)
        if self.group_id:
            filters["group_id"] = self.group_id
        if self.household_id:
            filters["household_id"] = self.household_id
        return filters

    async def _query(self) -> QuerySet[RecipeModel]:
        query = self.model.all()
        if self.group_id:
            query = query.filter(group_id=self.group_id)
        if self.household_id:
            query = query.filter(user__household_id=self.household_id)
        return query

    async def _serialize(self, entry: Model, schema: type[MealieModel] | None = None) -> Any:
        if not isinstance(entry, RecipeModel):
            raise TypeError("Expected a recipe")
        schema = schema or self.schema
        return schema.model_validate(await recipe_data(entry, summary=not issubclass(schema, Recipe)))

    @property
    def column_aliases(self):
        if not self.user_id:
            return {}

        return {
            "last_made": self._get_last_made_col_alias(),
            "rating": self._get_rating_col_alias(),
        }

    def by_user(self: Self, user_id: UUID4) -> Self:
        """Add a user_id to the repo, which will be used to handle recipe ratings and other user-specific data"""
        self.user_id = user_id
        return self

    def _get_last_made_col_alias(self) -> sa.ColumnElement | None:
        """
        Computed last_made which uses `HouseholdToRecipe.last_made` for the user's household,
        otherwise an arbitrarily low date
        """

        user_household_subquery = sa.select(User.household_id).where(User.id == self.user_id).scalar_subquery()
        last_made_subquery = (
            sa.select(HouseholdToRecipe.last_made)
            .where(
                HouseholdToRecipe.recipe_id == LegacyRecipe.id,
                HouseholdToRecipe.household_id == user_household_subquery,
            )
            .correlate(LegacyRecipe)
            .scalar_subquery()
        )
        return sa.func.coalesce(last_made_subquery, datetime(year=1900, month=1, day=1, tzinfo=UTC))

    def _get_rating_col_alias(self) -> sa.ColumnElement | None:
        """Computed rating which uses the user's rating if it exists, otherwise falling back to the recipe's rating"""

        effective_rating = sa.case(
            (
                sa.exists().where(
                    UserToRecipe.recipe_id == LegacyRecipe.id,
                    UserToRecipe.user_id == self.user_id,
                    UserToRecipe.rating != None,  # noqa E711
                    UserToRecipe.rating > 0,
                ),
                sa.select(sa.func.max(UserToRecipe.rating))
                .where(UserToRecipe.recipe_id == LegacyRecipe.id, UserToRecipe.user_id == self.user_id)
                .correlate(LegacyRecipe)
                .scalar_subquery(),
            ),
            else_=sa.case(
                (LegacyRecipe.rating == 0, None),
                else_=LegacyRecipe.rating,
            ),
        )
        return sa.cast(effective_rating, sa.Float)

    async def create(self, document: Recipe | BaseModel | dict[str, Any]) -> Recipe:
        data = document.copy() if isinstance(document, dict) else document.model_dump()
        original_name = data.get("name")
        for attempt in range(1, 11):
            try:
                async with in_transaction("default"):
                    values = {key: value for key, value in data.items() if key in self.model._meta.db_fields}
                    if values.get("id") is None:
                        values.pop("id", None)
                    if values.get("date_added") is None:
                        values["date_added"] = datetime.now(UTC).date()
                    values["date_updated"] = datetime.now(UTC)
                    entry = await self.model.create(**values)
                    await self._write_organizers(entry, data)
                    await replace_recipe_children(entry, data, creating=True)
                    await self._after_write(entry)
                    return await self._serialize(entry)
            except IntegrityError:
                data["name"] = f"{original_name} ({attempt})"
                data["slug"] = create_recipe_slug(data["name"])
                if isinstance(document, Recipe):
                    document.name, document.slug = data["name"], data["slug"]
                if attempt == 10:
                    raise
        raise RuntimeError("Could not create recipe")

    async def _resolve_organizer(
        self, model: type[Category] | type[Tag] | type[Tool], group_id: UUID, name: str
    ) -> Model:
        name = name.strip()
        for attempt in range(10):
            existing = await model.filter(group_id=group_id, name__iexact=name).first()
            if existing:
                return existing
            try:
                # A savepoint keeps a competing organizer insert from rolling
                # back the entire recipe or poisoning a PostgreSQL transaction.
                async with in_transaction("default"):
                    return await model.create(group_id=group_id, name=name, slug=slugify(name))
            except IntegrityError:
                if attempt == 9:
                    raise
        raise RuntimeError("Could not resolve organizer")

    async def _write_organizers(self, entry: RecipeModel, data: dict[str, Any]) -> None:
        for key, model in (("recipe_category", Category), ("tags", Tag), ("tools", Tool)):
            resolved = []
            for organizer in data.get(key) or []:
                identifier = organizer.get("id")
                existing = None
                if identifier:
                    try:
                        existing = await model.get_or_none(id=UUID(str(identifier)), group_id=entry.group_id)
                    except ValueError:
                        pass
                if existing is None and organizer.get("name"):
                    existing = await self._resolve_organizer(model, entry.group_id, organizer["name"])
                if existing is not None:
                    resolved.append(existing)
            relation = getattr(entry, key)
            await relation.clear()
            if resolved:
                await relation.add(*resolved)

    async def update(self, match_value: Any, new_data: dict[str, Any] | BaseModel) -> Recipe:
        data = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        async with in_transaction("default"):
            entry = await self._query_one(match_value)
            if name := data.get("name"):
                data["slug"] = entry.slug if name == entry.name else create_recipe_slug(name)
            data["slug"] = data.get("slug") or entry.slug
            for key in ("id", "user_id", "group_id"):
                data[key] = getattr(entry, key)
            values = {key: value for key, value in data.items() if key in self.model._meta.db_fields and key != "id"}
            values["date_updated"] = datetime.now(UTC)
            # Aggregate ratings are changed through the user-rating repository.
            # Legacy recipe writes only recalculated when the supplied value changed.
            if "rating" in values and values["rating"] != entry.rating:
                from tortoise.functions import Avg

                from mealie.db.models.users.user_to_recipe import UserToRecipe as NativeUserRating

                averages = (
                    await NativeUserRating.filter(recipe_id=entry.id, rating__gt=0)
                    .annotate(value=Avg("rating"))
                    .values("value")
                )
                values["rating"] = averages[0]["value"] if averages else None
            entry.update_from_dict(values)
            await entry.save()
            await self._write_organizers(entry, data)
            await replace_recipe_children(entry, data, creating=False)
            await self._after_write(entry)
            return await self._serialize(entry)

    async def delete_many(self, values: Iterable[Any]) -> list[Recipe]:
        async with in_transaction("default"):
            entries = await (await self._query()).filter(slug__in=list(values))
            return [await self.delete(entry.slug) for entry in entries]

    async def delete_all(self) -> None:
        await self.delete_many(await (await self._query()).values_list("slug", flat=True))

    async def update_image(self, slug: str, _: str | None = None) -> str:
        entry = await self._query_one(slug)
        entry.image = cache.new_key()
        await entry.save(update_fields=["image", "update_at"])
        await self._after_write(entry)
        return entry.image

    async def delete_image(self, slug: str, _: str | None = None) -> None:
        entry = await self._query_one(slug)
        entry.image = None
        await entry.save(update_fields=["image", "update_at"])
        await self._after_write(entry)

    async def count_uncategorized(self, count: bool = True, override_schema: type[MealieModel] | None = None) -> Any:
        return await self._count_organizer("recipe_category", count, override_schema)

    async def count_untagged(self, count: bool = True, override_schema: type[MealieModel] | None = None) -> Any:
        return await self._count_organizer("tags", count, override_schema)

    async def _count_organizer(self, field: str, count: bool, schema: type[MealieModel] | None) -> Any:
        query = (await self._query()).filter(**{field + "__id__isnull": True})
        return await query.count() if count else [await self._serialize(entry, schema) for entry in await query]

    async def _uuids_for_items(self, items: list[UUID | str] | None, model: Any) -> list[UUID] | None:
        if not items:
            return None
        ids, slugs = [], []
        for item in items:
            try:
                ids.append(UUID(str(item)))
            except ValueError:
                slugs.append(str(item))
        if slugs:
            ids.extend(await model.filter(slug__in=slugs).values_list("id", flat=True))
        return ids

    async def _search_query(self, query: sa.Select, search: str) -> sa.Select:
        parser = SearchFilter(SearchSession(), search, self.schema._normalize_search)  # type: ignore[arg-type]
        if parser.search_type is SearchType.fuzzy:
            ingredients = sa.select(LegacyIngredient.id).where(
                sa.or_(
                    LegacyIngredient.note_normalized.op("%>")(parser.search),
                    LegacyIngredient.original_text_normalized.op("%>")(parser.search),
                )
            )
            identifiers = [row["id"] for row in await execute_select(ingredients)]
            await connections.get("default").execute_query(
                f"SET pg_trgm.word_similarity_threshold = {self.schema._fuzzy_similarity_threshold}"
            )
            return query.where(
                sa.or_(
                    LegacyRecipe.name_normalized.op("%>")(parser.search),
                    LegacyRecipe.description_normalized.op("%>")(parser.search),
                    LegacyRecipe.recipe_ingredient.any(LegacyIngredient.id.in_(identifiers)),
                )
            ).order_by(sa.func.least(LegacyRecipe.name_normalized.op("<->>")(parser.search)))
        ingredients = sa.select(LegacyIngredient.id).where(
            sa.or_(
                *[LegacyIngredient.note_normalized.like(f"%{part}%") for part in parser.search_list],
                *[LegacyIngredient.original_text_normalized.like(f"%{part}%") for part in parser.search_list],
            )
        )
        identifiers = [row["id"] for row in await execute_select(ingredients)]
        return query.where(
            sa.or_(
                *[LegacyRecipe.name_normalized.like(f"%{part}%") for part in parser.search_list],
                *[LegacyRecipe.description_normalized.like(f"%{part}%") for part in parser.search_list],
                LegacyRecipe.recipe_ingredient.any(LegacyIngredient.id.in_(identifiers)),
            )
        ).order_by(sa.desc(LegacyRecipe.name_normalized.like(f"%{parser.search}%")))

    async def page_all(  # type: ignore[override]
        self,
        pagination: PaginationQuery,
        override: type[MealieModel] | None = None,
        cookbook: ReadCookBook | None = None,
        categories: list[UUID4 | str] | None = None,
        tags: list[UUID4 | str] | None = None,
        tools: list[UUID4 | str] | None = None,
        foods: list[UUID4 | str] | None = None,
        households: list[UUID4 | str] | None = None,
        require_all_categories: bool = True,
        require_all_tags: bool = True,
        require_all_tools: bool = True,
        require_all_foods: bool = True,
        search: str | None = None,
    ) -> RecipePagination:
        paging = pagination.model_copy()
        query = (
            sa.select(LegacyRecipe.id)
            .filter(LegacyRecipe.household_id.is_not(None))
            .filter_by(**self._filter_builder())
        )
        if cookbook:
            paging.query_filter = QueryFilterBuilder.combine_filters(paging.query_filter, cookbook.query_filter_string)
        else:
            query = query.filter(
                *self._build_recipe_filter(
                    categories=await self._uuids_for_items(categories, Category),
                    tags=await self._uuids_for_items(tags, Tag),
                    tools=await self._uuids_for_items(tools, Tool),
                    foods=foods,
                    households=await self._uuids_for_items(households, Household),
                    require_all_categories=require_all_categories,
                    require_all_tags=require_all_tags,
                    require_all_tools=require_all_tools,
                    require_all_foods=require_all_foods,
                )
            )
        if search:
            query = await self._search_query(query, search)
        try:
            identifiers = await query_identifiers(LegacyRecipe, paging, query=query, column_aliases=self.column_aliases)
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
        entries = {entry.id: entry for entry in await (await self._query()).filter(id__in=identifiers)}
        return RecipePagination(
            page=paging.page,
            per_page=paging.per_page,
            total=count,
            total_pages=pages,
            items=[await self._serialize(entries[UUID(str(key))], RecipeSummary) for key in identifiers],
        )

    @staticmethod
    def _ingredient_uses_food(food: UUID4) -> sa.ColumnElement:
        """
        An ingredient counts as using a food when it calls for it, or offers it as a substitute.

        The two are the same thing as far as the recipe is concerned: both are lost if the food
        goes away, which is what makes this the right question for the food delete warning.
        """

        return sa.or_(
            LegacyIngredient.food_id == food,
            LegacyIngredient.substitutions.any(LegacySubstitution.substitute_food_id == food),
        )

    @staticmethod
    def _ingredient_uses_any_food(foods: list[UUID4]) -> sa.ColumnElement:
        return sa.or_(
            LegacyIngredient.food_id.in_(foods),
            LegacyIngredient.substitutions.any(LegacySubstitution.substitute_food_id.in_(foods)),
        )

    def _build_recipe_filter(
        self,
        categories: list[UUID4] | None = None,
        tags: list[UUID4] | None = None,
        tools: list[UUID4] | None = None,
        foods: list[UUID4] | None = None,
        households: list[UUID4] | None = None,
        require_all_categories: bool = True,
        require_all_tags: bool = True,
        require_all_tools: bool = True,
        require_all_foods: bool = True,
    ) -> list:
        fltr: list[sa.ColumnElement] = []
        if self.group_id:
            fltr.append(LegacyRecipe.group_id == self.group_id)
        if self.household_id:
            fltr.append(LegacyRecipe.household_id == self.household_id)

        if categories:
            if require_all_categories:
                fltr.extend(LegacyRecipe.recipe_category.any(LegacyCategory.id == cat_id) for cat_id in categories)
            else:
                fltr.append(LegacyRecipe.recipe_category.any(LegacyCategory.id.in_(categories)))

        if tags:
            if require_all_tags:
                fltr.extend(LegacyRecipe.tags.any(LegacyTag.id == tag_id) for tag_id in tags)
            else:
                fltr.append(LegacyRecipe.tags.any(LegacyTag.id.in_(tags)))

        if tools:
            if require_all_tools:
                fltr.extend(LegacyRecipe.tools.any(LegacyTool.id == tool_id) for tool_id in tools)
            else:
                fltr.append(LegacyRecipe.tools.any(LegacyTool.id.in_(tools)))
        if foods:
            if require_all_foods:
                fltr.extend(LegacyRecipe.recipe_ingredient.any(self._ingredient_uses_food(food)) for food in foods)
            else:
                fltr.append(LegacyRecipe.recipe_ingredient.any(self._ingredient_uses_any_food(foods)))
        if households:
            fltr.append(LegacyRecipe.household_id.in_(households))
        return fltr

    async def get_random(self, limit: int = 1) -> list[Recipe]:
        query = (
            sa.select(LegacyRecipe.id)
            .filter(LegacyRecipe.household_id.is_not(None))
            .filter_by(**self._filter_builder())
        )
        identifiers = [row["id"] for row in await execute_select(query.order_by(sa.func.random()).limit(limit))]
        entries = {entry.id: entry for entry in await (await self._query()).filter(id__in=identifiers)}
        return [await self._serialize(entries[UUID(str(key))]) for key in identifiers]

    async def get_by_slug(self, group_id: UUID4, slug: str) -> Recipe | None:
        entry = await RecipeModel.get_or_none(group_id=group_id, slug=slug)
        return await self._serialize(entry) if entry else None

    async def all_ids(self, group_id: UUID4) -> Sequence[UUID4]:
        return await RecipeModel.filter(group_id=group_id).values_list("id", flat=True)
