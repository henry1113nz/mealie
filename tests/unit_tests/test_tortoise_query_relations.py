"""Correlated filters and ordering keep repeated native tables distinct."""

from uuid import UUID

import pytest

from mealie.core.settings import AppSettings
from mealie.db.models.group import Group
from mealie.db.models.recipe import (
    IngredientFoodModel,
    IngredientFoodSubstitutionModel,
    RecipeIngredientModel,
    RecipeModel,
)
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.repos._recipe_query import query_identifiers
from mealie.schema.response.pagination import OrderDirection, PaginationQuery
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_settings as server_settings


@pytest.mark.asyncio
async def test_referenced_recipe_filters_and_ordering_correlate_with_outer_recipe(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)):
        group = await Group.create(name="Repeated recipes")
        sauce = await RecipeModel.create(group_id=group.id, name="A sauce", slug="a-sauce")
        stock = await RecipeModel.create(group_id=group.id, name="Z stock", slug="z-stock")
        first = await RecipeModel.create(group_id=group.id, name="Z first", slug="z-first")
        second = await RecipeModel.create(group_id=group.id, name="A second", slug="a-second")
        await RecipeIngredientModel.create(recipe_id=first.id, referenced_recipe_id=sauce.id, position=0)
        await RecipeIngredientModel.create(recipe_id=second.id, referenced_recipe_id=stock.id, position=0)
        matches = await query_identifiers(
            RecipeModel,
            PaginationQuery(query_filter='recipe_ingredient.referenced_recipe.name = "A sauce"'),
            group_id=group.id,
        )
        assert [UUID(str(value)) for value in matches] == [first.id]
        ordered = await query_identifiers(
            RecipeModel,
            PaginationQuery(
                query_filter="recipe_ingredient.referenced_recipe.id IS NOT NULL",
                order_by="recipe_ingredient.referenced_recipe.name",
                order_direction=OrderDirection.asc,
            ),
            group_id=group.id,
        )
        assert [UUID(str(value)) for value in ordered] == [first.id, second.id]


@pytest.mark.asyncio
async def test_substitute_food_filters_and_ordering_correlate_with_outer_food(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)):
        group = await Group.create(name="Repeated foods")
        broth = await IngredientFoodModel.create(group_id=group.id, name="A broth")
        water = await IngredientFoodModel.create(group_id=group.id, name="Z water")
        first = await IngredientFoodModel.create(group_id=group.id, name="Z stock")
        second = await IngredientFoodModel.create(group_id=group.id, name="A stock")
        await IngredientFoodSubstitutionModel.create(food_id=first.id, substitute_food_id=broth.id, position=0)
        await IngredientFoodSubstitutionModel.create(food_id=second.id, substitute_food_id=water.id, position=0)
        matches = await query_identifiers(
            IngredientFoodModel,
            PaginationQuery(query_filter='substitutions.substitute_food.name = "A broth"'),
            group_id=group.id,
        )
        assert [UUID(str(value)) for value in matches] == [first.id]
        ordered = await query_identifiers(
            IngredientFoodModel,
            PaginationQuery(
                query_filter="substitutions.substitute_food.id IS NOT NULL",
                order_by="substitutions.substitute_food.name",
                order_direction=OrderDirection.asc,
            ),
            group_id=group.id,
        )
        assert [UUID(str(value)) for value in ordered] == [first.id, second.id]


@pytest.mark.asyncio
async def test_postgres_fuzzy_search_uses_transaction_local_threshold_for_both_random_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from uuid import uuid4

    from mealie.db.models.recipe import IngredientUnitModel
    from mealie.repos import _recipe_query
    from mealie.schema.recipe.recipe_ingredient import IngredientUnit
    from mealie.services.query_filter import sql

    active = False
    statements = []
    identifier = uuid4()

    async def execute_query(statement: str, parameters=None):
        assert active
        statements.append(statement)
        return 0, []

    async def execute_query_dict(statement: str, parameters=None):
        assert active
        statements.append(statement)
        return [{"id": identifier}]

    connection = SimpleNamespace(
        capabilities=SimpleNamespace(dialect="postgres"),
        execute_query=execute_query,
        execute_query_dict=execute_query_dict,
    )

    @asynccontextmanager
    async def transaction(name: str):
        nonlocal active
        assert name == "default"
        active = True
        try:
            yield connection
        finally:
            active = False

    connection_handler = SimpleNamespace(get=lambda _: connection)
    monkeypatch.setattr(_recipe_query, "connections", connection_handler)
    monkeypatch.setattr(sql, "connections", connection_handler)
    monkeypatch.setattr(_recipe_query, "in_transaction", transaction)
    identifiers = await query_identifiers(
        IngredientUnitModel,
        PaginationQuery(order_by="random", pagination_seed="seed"),
        search="tablespoon",
        schema=IngredientUnit,
    )
    assert identifiers == [identifier]
    assert not active
    assert statements[0] == "SET LOCAL pg_trgm.word_similarity_threshold = 0.5"
    assert len(statements) == 3
    assert all(statement.startswith("SELECT ") for statement in statements[1:])
