from collections.abc import Awaitable, Callable

from pydantic import BaseModel
from slugify import slugify

from mealie.repos.repository_factory import AllRepositories
from mealie.schema.recipe.recipe import RecipeCategory, RecipeTag, RecipeTool
from mealie.schema.recipe.recipe_category import CategorySave, TagSave
from mealie.schema.recipe.recipe_tool import RecipeToolSave
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.matching import find_match

ORGANIZER_FUZZY_MATCH_THRESHOLD = 90
"""
Deliberately stricter than the ingredient parser's thresholds. Attaching the wrong organizer is
worse than missing one, and near-misses are common among organizer names ("Vegan"/"Vegetarian").
"""


class OrganizerResolver:
    """
    Turns organizer names into database entities, matching against the group's existing
    organizers before creating anything new.
    """

    def __init__(self, repos: AllRepositories, fuzzy_match_threshold: int = ORGANIZER_FUZZY_MATCH_THRESHOLD) -> None:
        self.repos = repos
        self.fuzzy_match_threshold = fuzzy_match_threshold

        self._tags: dict[str, RecipeTag] | None = None
        self._categories: dict[str, RecipeCategory] | None = None
        self._tools: dict[str, RecipeTool] | None = None

    @staticmethod
    def _normalize(name: str) -> str:
        return slugify(name)

    async def _load[T: BaseModel](self, repo, schema: type[T]) -> dict[str, T]:
        query = PaginationQuery(page=1, per_page=-1)
        items = (await repo.page_all(query)).items
        return {self._normalize(item.name): schema.model_validate(item, from_attributes=True) for item in items}

    async def tags(self) -> dict[str, RecipeTag]:
        if self._tags is None:
            self._tags = await self._load(self.repos.tags, RecipeTag)

        return self._tags

    async def categories(self) -> dict[str, RecipeCategory]:
        if self._categories is None:
            self._categories = await self._load(self.repos.categories, RecipeCategory)

        return self._categories

    async def tools(self) -> dict[str, RecipeTool]:
        if self._tools is None:
            self._tools = await self._load(self.repos.tools, RecipeTool)

        return self._tools

    async def existing_names(self) -> dict[str, list[str]]:
        """The group's existing organizer names, for injecting into a prompt."""

        return {
            "tags": [tag.name for tag in (await self.tags()).values()],
            "categories": [category.name for category in (await self.categories()).values()],
            "tools": [tool.name for tool in (await self.tools()).values()],
        }

    async def _resolve[T: BaseModel](
        self,
        names: list[str],
        store: dict[str, T],
        create_missing: bool,
        create: Callable[[str], Awaitable[T]],
    ) -> list[T]:
        resolved: list[T] = []
        seen: set[str] = set()

        for name in names:
            name = name.strip()
            if not name:
                continue

            normalized = self._normalize(name)
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)

            match = find_match(normalized, store_map=store, fuzzy_match_threshold=self.fuzzy_match_threshold)
            if match:
                resolved.append(match)
                continue

            if not create_missing:
                continue

            created = await create(name)
            store[normalized] = created
            resolved.append(created)

        return resolved

    async def resolve_tags(self, names: list[str], create_missing: bool) -> list[RecipeTag]:
        async def create(name: str) -> RecipeTag:
            saved = await self.repos.tags.create(TagSave(name=name, group_id=self.repos.group_id))
            return RecipeTag.model_validate(saved, from_attributes=True)

        return await self._resolve(names, await self.tags(), create_missing, create)

    async def resolve_categories(self, names: list[str], create_missing: bool) -> list[RecipeCategory]:
        async def create(name: str) -> RecipeCategory:
            saved = await self.repos.categories.create(CategorySave(name=name, group_id=self.repos.group_id))
            return RecipeCategory.model_validate(saved, from_attributes=True)

        return await self._resolve(names, await self.categories(), create_missing, create)

    async def resolve_tools(self, names: list[str], create_missing: bool) -> list[RecipeTool]:
        async def create(name: str) -> RecipeTool:
            saved = await self.repos.tools.create(RecipeToolSave(name=name, group_id=self.repos.group_id))
            return RecipeTool.model_validate(saved, from_attributes=True)

        return await self._resolve(names, await self.tools(), create_missing, create)
