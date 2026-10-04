"""The Tortoise query filter must select exactly the rows the SQLAlchemy QueryFilterBuilder does.

Both run the same filter strings over the same data, and the matched ids are compared.
"""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from mealie.db.models.recipe.ingredient import IngredientUnitModel
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.tortoise import models as tm
from mealie.schema.recipe import Recipe
from mealie.schema.recipe.recipe_category import CategorySave, TagSave
from mealie.schema.recipe.recipe_ingredient import SaveIngredientUnit
from mealie.services.query_filter.builder import NonFilterableValueError, QueryFilterBuilder
from mealie.services.query_filter.tortoise_filter import TortoiseQueryFilter
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser


@pytest.fixture
def filter_data(unique_user: TestUser) -> dict:
    db = unique_user.repos
    tags = [
        db.tags.create(TagSave(group_id=unique_user.group_id, name=n, slug=n))
        for n in (f"tf-{x}-{random_string(6)}" for x in "abc")
    ]
    cats = [
        db.categories.create(CategorySave(group_id=unique_user.group_id, name=n, slug=n))
        for n in (f"cf-{x}-{random_string(6)}" for x in "ab")
    ]
    combos = [
        ([], []),
        ([tags[0]], [cats[0]]),
        ([tags[0], tags[1]], [cats[1]]),
        ([tags[1], tags[2]], [cats[0], cats[1]]),
        ([tags[2]], []),
    ]
    recipes = []
    for i, (recipe_tags, recipe_cats) in enumerate(combos):
        recipes.append(
            db.recipes.create(
                Recipe(
                    user_id=unique_user.user_id,
                    group_id=unique_user.group_id,
                    name=f"Filter Soup {i} {random_string(5)}",
                    tags=recipe_tags,
                    recipe_category=recipe_cats,
                    rating=i,
                )
            )
        )
    units = [
        db.ingredient_units.create(
            SaveIngredientUnit(
                group_id=unique_user.group_id, name=f"unit-{i}-{random_string(4)}", use_abbreviation=i % 2 == 0
            )
        )
        for i in range(4)
    ]
    return {"tags": tags, "cats": cats, "recipes": recipes, "units": units}


def _recipe_filters(d: dict) -> list[str]:
    t, c, r = d["tags"], d["cats"], d["recipes"]
    since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    return [
        f"tags.name IN [{t[0].name}]",
        f"tags.name IN [{t[0].name}, {t[2].name}]",
        f"tags.name NOT IN [{t[0].name}]",
        f"tags.name CONTAINS ALL [{t[0].name}, {t[1].name}]",
        f"tags.name CONTAINS ALL [{t[1].name}]",
        f"tags.name IN [{t[0].name}] AND tags.name IN [{t[1].name}]",
        f"recipeCategory.name IN [{c[0].name}]",
        f"recipeCategory.name NOT IN [{c[0].name}]",
        f'recipeCategory.id = "{c[1].id}"',
        f"tags.name IN [{t[0].name}] OR recipeCategory.name IN [{c[0].name}]",
        f"(tags.name IN [{t[0].name}] OR tags.name IN [{t[2].name}]) AND recipeCategory.name IN [{c[1].name}]",
        f"tags.name IN [{t[2].name}] AND recipeCategory.name IN [{c[0].name}] OR rating > 3",
        f'name = "{r[1].name.upper()}"',
        f'name <> "{r[1].name}"',
        'name LIKE "%soup 2%"',
        'name LIKE "filter%"',
        'name NOT LIKE "%soup 1%"',
        "rating > 2",
        "rating <= 1",
        "rating IN [1, 3]",
        f'createdAt >= "{since}"',
        f'createdAt < "{since}"',
        "orgURL IS NULL",
        "orgURL IS NOT NULL",
    ]


def _unit_filters(d: dict) -> list[str]:
    u = d["units"]
    return [
        "useAbbreviation = true",
        "useAbbreviation = false",
        f"name IN [{u[0].name}, {u[1].name}]",
        f"name NOT IN [{u[0].name}, {u[1].name}]",
    ]


def _sqlalchemy_ids(session, model, group_id, filter_string: str) -> set:
    query = sa.select(model.id).where(model.group_id == group_id)
    query = QueryFilterBuilder(filter_string).filter_query(query, model=model)
    return set(session.execute(query).scalars().all())


def _tortoise_ids(api_client: TestClient, model, group_id, filter_string: str) -> set:
    async def run():
        query = TortoiseQueryFilter(filter_string).apply(model.filter(group_id=group_id), model)
        return set(await query.values_list("id", flat=True))

    return api_client.portal.call(run)  # type: ignore[union-attr]


@pytest.mark.parametrize("which", ["recipes", "units"])
def test_tortoise_filter_matches_sqlalchemy(
    api_client: TestClient, unique_user: TestUser, filter_data: dict, which: str
):
    session = unique_user.repos.session
    if which == "recipes":
        filters, sa_model, tt_model = _recipe_filters(filter_data), RecipeModel, tm.RecipeModel
    else:
        filters, sa_model, tt_model = _unit_filters(filter_data), IngredientUnitModel, tm.IngredientUnitModel

    for filter_string in filters:
        expected = _sqlalchemy_ids(session, sa_model, unique_user.group_id, filter_string)
        actual = _tortoise_ids(api_client, tt_model, unique_user.group_id, filter_string)
        assert actual == expected, filter_string


def test_tortoise_filter_rejects_non_filterable_columns(api_client: TestClient):
    with pytest.raises(NonFilterableValueError):
        TortoiseQueryFilter('user.password = "x"').condition(tm.RecipeModel)
