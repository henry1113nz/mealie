from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException
from pydantic import UUID4

from mealie.db.models.recipe.ingredient import IngredientFoodModel
from mealie.db.models.recipe.tool import Tool
from mealie.db.models.users.users import User
from mealie.schema.recipe.recipe import RecipeSummary
from mealie.schema.recipe.recipe_ingredient import IngredientFood, IngredientFoodSummary
from mealie.schema.recipe.recipe_suggestion import (
    RecipeSuggestionQuery,
    RecipeSuggestionResponseItem,
    RecipeSuggestionSubstitutedFood,
)
from mealie.services.query_filter.builder import QueryFilterBuilder


class RecipeSuggestionMixin:
    """Rank scoped recipes by available tools, ingredients and substitutions."""

    if TYPE_CHECKING:
        from tortoise.backends.base.client import BaseDBAsyncClient
        from tortoise.queryset import QuerySet

        from mealie.db.models.recipe.recipe import RecipeModel
        from mealie.schema.response.pagination import RequestQuery

        model: type[RecipeModel]
        session: BaseDBAsyncClient
        user_id: UUID4 | None

        @property
        def column_aliases(self) -> dict[str, str]: ...

        def _query(self, override_schema=None, with_options=True) -> QuerySet: ...
        def _filter_builder(self, **kwargs) -> dict[str, Any]: ...
        async def add_order_by_to_query(self, query: QuerySet, request_query: RequestQuery) -> QuerySet: ...

    @staticmethod
    def _find_substitute_on_hand(ingredient: Any, food: Any, on_hand_food_ids: set[UUID4]) -> Any:
        for substitution in [*ingredient.substitutions, *food.substitutions]:
            if substitution.substitute_food_id in on_hand_food_ids:
                return substitution.substitute_food
        return None

    async def _with_on_hand_ids(
        self, params: RecipeSuggestionQuery, user_food_ids: list[UUID4], user_tool_ids: list[UUID4]
    ) -> tuple[list[UUID4], list[UUID4]]:
        food_ids, tool_ids = set(user_food_ids), set(user_tool_ids)
        if self.user_id:
            user = await User.all().using_db(self.session).get(id=self.user_id)
            if params.include_foods_on_hand:
                food_ids.update(
                    cast(
                        list[UUID4],
                        await IngredientFoodModel.filter(households_with_ingredient_food__id=user.household_id)
                        .using_db(self.session)
                        .values_list("id", flat=True),
                    )
                )
            if params.include_tools_on_hand:
                tool_ids.update(
                    cast(
                        list[UUID4],
                        await Tool.filter(households_with_tool__id=user.household_id)
                        .using_db(self.session)
                        .values_list("id", flat=True),
                    )
                )
        return list(food_ids), list(tool_ids)

    async def find_suggested_recipes(
        self,
        params: RecipeSuggestionQuery,
        food_ids: list[UUID4] | None = None,
        tool_ids: list[UUID4] | None = None,
    ) -> list[RecipeSuggestionResponseItem]:
        params = params.model_copy()
        params.order_by = params.order_by or "created_at"
        user_food_ids, user_tool_ids = set(food_ids or []), set(tool_ids or [])
        available_food_ids, available_tool_ids = await self._with_on_hand_ids(
            params, list(user_food_ids), list(user_tool_ids)
        )
        available_foods, available_tools = set(available_food_ids), set(available_tool_ids)
        query = self._query().filter(user__household_id__isnull=False, **self._filter_builder())
        if params.query_filter:
            try:
                query = QueryFilterBuilder(params.query_filter).filter_query(query, self.model, self.column_aliases)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
        query = await self.add_order_by_to_query(query, params)
        # Fetch the graph in batches; every ingredient and substitution is then
        # traversed without issuing a query for each related row.
        query = query.prefetch_related(
            "tools",
            "recipe_ingredient__substitutions__substitute_food",
            "recipe_ingredient__food__substitutions__substitute_food",
        )
        ranked: list[tuple[tuple[int, ...], RecipeSuggestionResponseItem]] = []
        for recipe in await query:
            missing_tools = [tool for tool in recipe.tools if tool.id not in available_tools] if user_tool_ids else []
            if user_tool_ids and len(missing_tools) > params.max_missing_tools:
                continue
            missing_foods, substituted_foods = [], []
            missing_count = direct_matches = substituted_matches = 0
            seen_food_ids = set(available_foods)
            if user_food_ids:
                for ingredient in recipe.recipe_ingredient:
                    food = ingredient.food
                    if food is None:
                        continue
                    direct_matches += food.id in user_food_ids
                    if params.include_substitutions and food.id not in user_food_ids:
                        substituted_matches += (
                            self._find_substitute_on_hand(ingredient, food, user_food_ids) is not None
                        )
                    substitute = None
                    if food.id not in available_foods:
                        if params.include_substitutions:
                            substitute = self._find_substitute_on_hand(ingredient, food, available_foods)
                        missing_count += substitute is None
                    if food.id in seen_food_ids:
                        continue
                    seen_food_ids.add(food.id)
                    food_schema = await food.to_schema(IngredientFood)
                    if substitute:
                        substituted_foods.append(
                            RecipeSuggestionSubstitutedFood(
                                food=food_schema, substitute_food=await substitute.to_schema(IngredientFoodSummary)
                            )
                        )
                    else:
                        missing_foods.append(food_schema)
                if missing_count > params.max_missing_foods or not (direct_matches or substituted_matches):
                    continue
            summary = await recipe.to_schema(RecipeSummary)
            missing_ids = {tool.id for tool in missing_tools}
            suggestion = RecipeSuggestionResponseItem(
                recipe=summary,
                missing_foods=missing_foods,
                substituted_foods=substituted_foods,
                missing_tools=[tool for tool in summary.tools or [] if tool.id in missing_ids],
            )
            ranked.append(((len(missing_tools), missing_count, -direct_matches, -substituted_matches), suggestion))
        ranked.sort(key=lambda item: item[0])
        return [item for _, item in ranked[: params.limit]]
