import logging
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from fastapi import HTTPException
from pydantic import UUID4

from mealie.db.models.household.household import Household
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.users import User
from mealie.schema.recipe.recipe import Recipe, RecipeSummary
from mealie.schema.recipe.recipe_ingredient import IngredientFood, IngredientFoodSummary, RecipeIngredient
from mealie.schema.recipe.recipe_suggestion import (
    RecipeSuggestionQuery,
    RecipeSuggestionResponseItem,
    RecipeSuggestionSubstitutedFood,
)
from mealie.schema.recipe.recipe_tool import RecipeToolOut
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.query_filter.sql import Expression, NativeQuery

from ._recipe_persistence import recipe_data
from ._recipe_query import query_identifiers

if TYPE_CHECKING:
    from tortoise.backends.base.client import BaseDBAsyncClient as Session


class RecipeSuggestionMixin:
    """
    The recipe finder, mixed into RepositoryRecipes.

    Split out because it is close to half of what that module would otherwise be, and the
    only part of it that is not ordinary CRUD and search. It owns no state; everything it
    reads belongs to the repository it is mixed into, and is declared below.

    Those declarations are type-checking only, so they add no class attributes and cannot
    shadow the real implementations through the MRO at runtime.
    """

    if TYPE_CHECKING:
        model: type[RecipeModel]
        session: Session
        logger: logging.Logger
        user_id: UUID4 | None
        group_id: UUID4 | None
        household_id: UUID4 | None

        def _filter_builder(self, **kwargs) -> dict[str, Any]: ...

        def _log_exception(self, e: Exception) -> None: ...

        def _base_query(self) -> NativeQuery: ...

    @staticmethod
    def _find_substitute_on_hand(
        ingredient: RecipeIngredient, food: IngredientFood, on_hand_food_ids: set[UUID4]
    ) -> IngredientFoodSummary | None:
        """
        The first substitute food the user has on hand, or None.

        Recipe-level substitutions are checked before the food's own, since they were written
        about this recipe specifically. A note-only substitution has no food id, and `None` is
        never in the on-hand set, so it can never satisfy an ingredient.
        """

        for substitution in [*ingredient.substitutions, *food.substitutions]:
            if substitution.substitute_food_id in on_hand_food_ids:
                return substitution.substitute_food

        return None

    @staticmethod
    def _covered_by_substitution(food_ids: list[UUID4]) -> Expression:
        if not food_ids:
            return Expression("FALSE")
        placeholders = ", ".join("?" for _ in food_ids)
        return Expression(
            "(EXISTS (SELECT 1 FROM ingredient_foods_substitutions fs "
            "WHERE fs.food_id = ri.food_id AND fs.substitute_food_id IN (" + placeholders + ")) "
            "OR EXISTS (SELECT 1 FROM recipes_ingredients_substitutions rs "
            "WHERE rs.ingredient_id = ri.id AND rs.substitute_food_id IN (" + placeholders + ")))",
            [*food_ids, *food_ids],
        )

    async def _with_on_hand_ids(
        self, params: RecipeSuggestionQuery, user_food_ids: list[UUID4], user_tool_ids: list[UUID4]
    ) -> tuple[list[UUID4], list[UUID4]]:
        food_ids, tool_ids = user_food_ids.copy(), user_tool_ids.copy()
        if self.user_id:
            user = await User.get_or_none(id=self.user_id)
            household = await Household.get_or_none(id=user.household_id) if user and user.household_id else None
            if household:
                if params.include_foods_on_hand:
                    food_ids = list(
                        dict.fromkeys(
                            [*food_ids, *await household.ingredient_foods_on_hand.all().values_list("id", flat=True)]
                        )
                    )
                if params.include_tools_on_hand:
                    tool_ids = list(
                        dict.fromkeys([*tool_ids, *await household.tools_on_hand.all().values_list("id", flat=True)])
                    )
        return food_ids, tool_ids

    @staticmethod
    def _membership(column: str, values: list[UUID4], *, negate: bool = False) -> Expression:
        if not values:
            return Expression("TRUE" if negate else "FALSE")
        return Expression(f"{column} {'NOT ' if negate else ''}IN ({', '.join('?' for _ in values)})", list(values))

    def _filter_suggestions_by_tools(
        self, query: NativeQuery, params: RecipeSuggestionQuery, tool_ids: list[UUID4]
    ) -> NativeQuery:
        unmatched = self._membership("rt.tool_id", tool_ids, negate=True)
        count = Expression(
            "(SELECT COUNT(*) FROM recipes_to_tools rt WHERE rt.recipe_id = recipes.id AND " + unmatched.sql + ")",
            unmatched.parameters,
        )
        return query.filter(Expression(count.sql + " <= ?", count.parameters + [params.max_missing_tools])).order_by(
            count.asc()
        )

    def _food_count(self, condition: Expression) -> Expression:
        return Expression(
            "(SELECT COUNT(*) FROM recipes_ingredients ri WHERE ri.recipe_id = recipes.id "
            "AND ri.food_id IS NOT NULL AND " + condition.sql + ")",
            condition.parameters,
        )

    def _filter_suggestions_by_foods(
        self, query: NativeQuery, params: RecipeSuggestionQuery, user_food_ids: list[UUID4], food_ids: list[UUID4]
    ) -> NativeQuery:
        missing = self._membership("ri.food_id", food_ids, negate=True)
        if params.include_substitutions:
            missing = missing & ~self._covered_by_substitution(food_ids)
        unmatched = self._food_count(missing)
        matched = self._food_count(self._membership("ri.food_id", user_food_ids))
        query.filter(Expression("EXISTS (SELECT 1 FROM recipe_settings WHERE recipe_settings.recipe_id = recipes.id)"))
        query.filter(Expression(unmatched.sql + " <= ?", unmatched.parameters + [params.max_missing_foods]))
        query.order_by(unmatched.asc(), matched.desc())
        at_least_one = Expression(matched.sql + " > 0", matched.parameters)
        if params.include_substitutions:
            substituted = self._food_count(
                self._membership("ri.food_id", user_food_ids, negate=True)
                & self._covered_by_substitution(user_food_ids)
            )
            query.order_by(substituted.desc())
            at_least_one = at_least_one | Expression(substituted.sql + " > 0", substituted.parameters)
        return query.filter(at_least_one)

    def _missing_and_substituted_foods(
        self, recipe: Recipe, params: RecipeSuggestionQuery, on_hand_food_ids: set[UUID4]
    ) -> tuple[list[IngredientFood], list[RecipeSuggestionSubstitutedFood]]:
        """
        Splits the recipe's foods the user lacks into the ones a substitute covers and the
        ones nothing covers, using the same satisfaction rule the query ranked on. Judged any
        other way, a food the query counted as covered gets reported back as missing.
        """

        missing_foods: list[IngredientFood] = []
        substituted_foods: list[RecipeSuggestionSubstitutedFood] = []

        seen_food_ids: set[UUID4] = set(on_hand_food_ids)
        for ingredient in recipe.recipe_ingredient:
            if not ingredient.food:
                continue
            if ingredient.food.id in seen_food_ids:
                continue

            seen_food_ids.add(ingredient.food.id)

            substitute = (
                self._find_substitute_on_hand(ingredient, ingredient.food, on_hand_food_ids)
                if params.include_substitutions
                else None
            )
            if substitute:
                substituted_foods.append(
                    RecipeSuggestionSubstitutedFood(
                        food=IngredientFood.model_validate(ingredient.food),
                        substitute_food=IngredientFoodSummary.model_validate(substitute),
                    )
                )
            else:
                missing_foods.append(IngredientFood.model_validate(ingredient.food))

        return missing_foods, substituted_foods

    @staticmethod
    def _missing_tools(recipe: Recipe, on_hand_tool_ids: set[UUID4]) -> list[RecipeToolOut]:
        missing_tools: list[RecipeToolOut] = []

        seen_tool_ids: set[UUID4] = set(on_hand_tool_ids)
        for tool in recipe.tools:
            if tool.id in seen_tool_ids:
                continue

            seen_tool_ids.add(tool.id)
            missing_tools.append(RecipeToolOut.model_validate(tool))

        return missing_tools

    async def find_suggested_recipes(
        self,
        params: RecipeSuggestionQuery,
        food_ids: list[UUID4] | None = None,
        tool_ids: list[UUID4] | None = None,
    ) -> list[RecipeSuggestionResponseItem]:
        """
        Queries all recipes and returns the ones that are missing the least amount of foods and tools.

        Results are ordered first by number of missing tools, then foods, and finally by the user-specified order.
        If foods are provided, the query will prefer recipes with more matches to user-provided foods.
        """

        if not params.order_by:
            params.order_by = "created_at"

        user_food_ids = list(set(food_ids or []))
        user_tool_ids = list(set(tool_ids or []))
        food_ids_with_on_hand, tool_ids_with_on_hand = await self._with_on_hand_ids(
            params, user_food_ids, user_tool_ids
        )

        q = self._base_query()
        if user_tool_ids:
            q = self._filter_suggestions_by_tools(q, params, tool_ids_with_on_hand)
        if user_food_ids:
            q = self._filter_suggestions_by_foods(q, params, user_food_ids, food_ids_with_on_hand)
        try:
            identifiers = await query_identifiers(RecipeModel, cast(PaginationQuery, params), query=q)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        identifiers = identifiers[: params.limit]
        entries = {entry.id: entry for entry in await RecipeModel.filter(id__in=identifiers)}
        data = [Recipe.model_validate(await recipe_data(entries[UUID(str(key))])) for key in identifiers]

        on_hand_food_ids = set(food_ids_with_on_hand)
        on_hand_tool_ids = set(tool_ids_with_on_hand)

        suggestions: list[RecipeSuggestionResponseItem] = []
        for result in data:
            recipe = result

            # only check for missing foods and tools if the user has provided a list of them
            missing_foods, substituted_foods = (
                self._missing_and_substituted_foods(recipe, params, on_hand_food_ids) if user_food_ids else ([], [])
            )
            missing_tools = self._missing_tools(recipe, on_hand_tool_ids) if user_tool_ids else []

            suggestions.append(
                RecipeSuggestionResponseItem(
                    recipe=RecipeSummary.model_validate(recipe),
                    missing_foods=missing_foods,
                    substituted_foods=substituted_foods,
                    missing_tools=missing_tools,
                )
            )

        return suggestions
