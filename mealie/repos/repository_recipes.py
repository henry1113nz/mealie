from collections.abc import Iterable, Sequence
from typing import Self, cast
from uuid import UUID

from pydantic import UUID4, BaseModel
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q, RawSQL, Subquery

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models.household import Household
from mealie.db.models.recipe.category import Category
from mealie.db.models.recipe.ingredient import RecipeIngredientModel
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.tag import Tag
from mealie.db.models.recipe.tool import Tool
from mealie.pkgs import cache
from mealie.schema.cookbook.cookbook import ReadCookBook
from mealie.schema.recipe import Recipe
from mealie.schema.recipe.recipe import RecipePagination, RecipeSummary, create_recipe_slug
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.query_filter.builder import QueryFilterBuilder

from ._recipe_suggestions import RecipeSuggestionMixin
from .repository_generic import HouseholdRepositoryGeneric


class RepositoryRecipes(RecipeSuggestionMixin, HouseholdRepositoryGeneric[Recipe, RecipeModel]):
    user_id: UUID4 | None = None

    @property
    def column_aliases(self) -> dict[str, str]:
        return {"last_made": "_effective_last_made", "rating": "_effective_rating"} if self.user_id else {}

    def by_user(self: Self, user_id: UUID4) -> Self:
        self.user_id = user_id
        return self

    def _query(self, override_schema=None, with_options=True):
        query = super()._query(override_schema, with_options).select_related("user")
        if self.user_id:
            # UUID is validated before interpolation. Native database UUID values
            # are encoded by the field for the selected backend.
            user_id = str(UUID(str(self.user_id)))
            query = query.annotate(
                _effective_last_made=RawSQL(
                    "COALESCE((SELECT hr.last_made FROM households_to_recipes hr "
                    "WHERE hr.recipe_id = recipes.id AND hr.household_id = "
                    f"(SELECT household_id FROM users WHERE id = '{user_id}')), '1900-01-01 00:00:00+00:00')"
                ),
                _effective_rating=RawSQL(
                    "COALESCE((SELECT MAX(ur.rating) FROM users_to_recipes ur "
                    f"WHERE ur.recipe_id = recipes.id AND ur.user_id = '{user_id}' AND ur.rating > 0), "
                    "NULLIF(recipes.rating, 0))"
                ),
            )
        return query

    async def create(self, document: Recipe | BaseModel | dict) -> Recipe:
        if not isinstance(document, Recipe):
            document = Recipe.model_validate(document if isinstance(document, dict) else document.model_dump())
        original_name = document.name
        for attempt in range(1, 11):
            try:
                return await super().create(document)
            except IntegrityError:
                if attempt >= 10:
                    raise
                document.name = f"{original_name} ({attempt})"
                document.slug = create_recipe_slug(document.name)
        raise RuntimeError("Unable to create recipe")

    async def delete_many(self, values: Iterable) -> list[Recipe]:
        entries = await self._query().filter(slug__in=list(values), **self._filter_builder())
        return [await self.delete(entry.slug) for entry in entries]

    async def update_image(self, slug: str, _: str | None = None) -> str:
        entry = await self._query_one(slug)
        entry.image = cache.new_key()
        await entry.save(using_db=self.session)
        return entry.image

    async def delete_image(self, slug: str, _: str | None = None) -> None:
        entry = await self._query_one(slug)
        entry.image = None
        await entry.save(using_db=self.session)

    async def count_uncategorized(self, count=True, override_schema=None):
        return await self._count_attribute("recipe_category", count=count, override_schema=override_schema)

    async def count_untagged(self, count=True, override_schema=None):
        return await self._count_attribute("tags", count=count, override_schema=override_schema)

    async def _uuids_for_items(self, items: list[UUID | str] | None, model: type[TortoiseModel]) -> list[UUID] | None:
        if not items:
            return None
        ids, slugs = [], []
        for item in items:
            try:
                ids.append(item if isinstance(item, UUID) else UUID(item))
            except ValueError:
                slugs.append(item)
        if slugs:
            filters: dict = {"slug__in": slugs}
            if self.group_id:
                filters["group_id"] = self.group_id
            ids.extend(
                cast(list[UUID], await model.filter(**filters).using_db(self.session).values_list("id", flat=True))
            )
        return ids

    async def _resolve_organizer(self, model: type[Tag] | type[Category] | type[Tool], name: str) -> dict:
        name = name.strip()
        for attempt in range(10):
            entry = await model.filter(group_id=self.group_id, name__iexact=name).using_db(self.session).first()
            if entry is None:
                try:
                    entry = await model.create_from_data(
                        {"name": name, "group_id": self.group_id}, using_db=self.session
                    )
                except IntegrityError:
                    if attempt == 9:
                        raise
                    continue
            return {"id": str(entry.id), "group_id": str(entry.group_id), "name": entry.name, "slug": entry.slug}
        raise RuntimeError(f"Failed to resolve organizer '{name}'")

    async def update(self, match_value: str | int | UUID4, new_data: BaseModel | dict) -> Recipe:
        data = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        entry = await self._query_one(match_value)
        if name := data.get("name"):
            data["slug"] = entry.slug if name == entry.name else create_recipe_slug(name)
        for field in ("id", "user_id", "household_id", "group_id"):
            data[field] = getattr(entry, field)
        data["slug"] = data.get("slug") or entry.slug
        organizers: dict[str, type[Tag] | type[Category] | type[Tool]] = {
            "tags": Tag,
            "recipe_category": Category,
            "tools": Tool,
        }
        for field, model in organizers.items():
            resolved = []
            for organizer in data.get(field) or []:
                existing = None
                if organizer.get("id"):
                    try:
                        organizer_id = UUID(str(organizer["id"]))
                    except ValueError:
                        organizer_id = None
                    if organizer_id:
                        existing = (
                            await model.filter(id=organizer_id, group_id=self.group_id).using_db(self.session).first()
                        )
                if existing:
                    resolved.append(
                        {"id": existing.id, "group_id": existing.group_id, "name": existing.name, "slug": existing.slug}
                    )
                elif organizer.get("name"):
                    resolved.append(await self._resolve_organizer(model, organizer["name"]))
            data[field] = resolved
        return await super().update(match_value, data)

    async def page_all(
        self,
        pagination: PaginationQuery,
        override=None,
        cookbook: ReadCookBook | None = None,
        categories: list[UUID4 | str] | None = None,
        tags: list[UUID4 | str] | None = None,
        tools: list[UUID4 | str] | None = None,
        foods: list[UUID4 | str] | None = None,
        households: list[UUID4 | str] | None = None,
        require_all_categories=True,
        require_all_tags=True,
        require_all_tools=True,
        require_all_foods=True,
        search: str | None = None,
    ) -> RecipePagination:
        pagination = pagination.model_copy()
        query = self._query().filter(user__household_id__isnull=False, **self._filter_builder())
        if cookbook:
            pagination.query_filter = QueryFilterBuilder.combine_filters(
                pagination.query_filter, cookbook.query_filter_string
            )
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
            query = self.add_search_to_query(query, self.schema, search)
        if not pagination.order_by and not search:
            pagination.order_by = "created_at"
        query, count, pages = await self.add_pagination_to_query(query, pagination)
        return RecipePagination(
            page=pagination.page,
            per_page=pagination.per_page,
            total=count,
            total_pages=pages,
            items=await self._to_schemas(await query, override or RecipeSummary),
        )

    @staticmethod
    def _ingredient_uses_food(food: UUID4) -> Q:
        return Q(food_id=food) | Q(substitutions__substitute_food_id=food)

    @staticmethod
    def _ingredient_uses_any_food(foods: list[UUID4]) -> Q:
        return Q(food_id__in=foods) | Q(substitutions__substitute_food_id__in=foods)

    def _build_recipe_filter(
        self,
        categories=None,
        tags=None,
        tools=None,
        foods=None,
        households=None,
        require_all_categories=True,
        require_all_tags=True,
        require_all_tools=True,
        require_all_foods=True,
    ) -> list[Q]:
        filters = []
        for path, values, require_all in [
            ("recipe_category", categories, require_all_categories),
            ("tags", tags, require_all_tags),
            ("tools", tools, require_all_tools),
        ]:
            if values:
                for required in ([value] for value in values) if require_all else [values]:
                    filters.append(Q(id__in=Subquery(self.model.filter(**{path + "__id__in": required}).values("id"))))
        if foods:
            for required in ([food] for food in foods) if require_all_foods else [foods]:
                filters.append(
                    Q(
                        id__in=Subquery(
                            RecipeIngredientModel.filter(self._ingredient_uses_any_food(required)).values("recipe_id")
                        )
                    )
                )
        if households:
            filters.append(Q(user__household_id__in=households))
        return filters

    async def get_random(self, limit=1) -> list[Recipe]:
        query = (
            self._query()
            .filter(user__household_id__isnull=False, **self._filter_builder())
            .annotate(_random=RawSQL("RANDOM()"))
            .order_by("_random")
            .limit(limit)
        )
        return await self._to_schemas(await query)

    async def get_by_slug(self, group_id: UUID4, slug: str) -> Recipe | None:
        entry = await self._query().filter(group_id=group_id, slug=slug).first()
        return await self._to_schema(entry) if entry is not None else None

    async def all_ids(self, group_id: UUID4) -> Sequence[UUID4]:
        return await self._query().filter(group_id=group_id).values_list("id", flat=True)
