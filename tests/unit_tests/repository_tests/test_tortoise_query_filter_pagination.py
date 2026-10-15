"""Parity checks for the async Tortoise query path (legacy regressions stay separate)."""

from __future__ import annotations

import sqlite3
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mealie.db.models import _all_models as _legacy_models  # noqa: F401
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.tortoise_models import Group, Recipe, Tag, User
from mealie.db.tortoise_setup import tortoise_close, tortoise_init
from mealie.repos.tortoise_repository import AsyncRepository
from mealie.schema.response.pagination import OrderByNullPosition, OrderDirection, PaginationQuery
from mealie.services.query_filter.builder import NonFilterableValueError, QueryFilterBuilder
from mealie.services.query_filter.tortoise import TortoiseFilterCompiler, validate_order_path


class RecipeResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


@pytest_asyncio.fixture
async def tortoise_recipe_db(tmp_path):
    db_path = tmp_path / "stage7.sqlite3"
    await tortoise_init(f"sqlite://{db_path}", create_schema=True)
    try:
        yield db_path
    finally:
        await tortoise_close()


async def create_group(name: str = "stage7") -> Group:
    return await Group.create(id=uuid4(), name=name, slug=name)


async def create_recipe(group: Group, name: str, tags: list[Tag] | None = None, rating: float | None = 1) -> Recipe:
    recipe = await Recipe.create(id=uuid4(), group=group, name=name, name_normalized=name.casefold(), rating=rating)
    if tags:
        await recipe.tags.add(*tags)
    return recipe


def legacy_ids(db_path, query) -> set[UUID]:
    connection = sqlite3.connect(db_path)
    try:
        sql = str(query.compile(compile_kwargs={"literal_binds": True}))
        return {UUID(row[0]) for row in connection.execute(sql).fetchall()}
    finally:
        connection.close()


@pytest.mark.asyncio
async def test_tortoise_filterability_matches_legacy_field_policy(tortoise_recipe_db):
    # New-path checks: direct and relationship fields, plus the same policy for ordering.
    with pytest.raises(NonFilterableValueError):
        TortoiseFilterCompiler.compile('password = "secret"', User)
    with pytest.raises(NonFilterableValueError):
        TortoiseFilterCompiler.compile('email = "private@example.test"', User)
    with pytest.raises(NonFilterableValueError):
        TortoiseFilterCompiler.compile('user.email = "private@example.test"', Recipe)
    with pytest.raises(NonFilterableValueError):
        validate_order_path(User, "password")

    TortoiseFilterCompiler.compile('full_name = "Visible Name"', User)
    assert validate_order_path(User, "full_name")[0] == "full_name"


@pytest.mark.asyncio
async def test_related_not_in_is_anti_existence_but_scalar_not_in_keeps_sql_null_semantics(tortoise_recipe_db):
    group = await create_group()
    excluded_tag = await Tag.create(id=uuid4(), group=group, name="excluded", slug="excluded")
    other_tag = await Tag.create(id=uuid4(), group=group, name="other", slug="other")
    matching = await create_recipe(group, "matching", [excluded_tag, other_tag])
    nonmatching = await create_recipe(group, "nonmatching", [other_tag])
    empty = await create_recipe(group, "empty")
    null_scalar = await create_recipe(group, "null-scalar", rating=None)
    numeric_scalar = await create_recipe(group, "numeric-scalar", rating=5)

    repo = AsyncRepository(Recipe, RecipeResult, group_id=group.id)
    related = await repo.page_all(
        PaginationQuery(per_page=-1, query_filter='tags.name NOT IN ["excluded"]', order_by="name")
    )
    related_ids = {item.id for item in related.items}
    assert matching.id not in related_ids
    assert nonmatching.id in related_ids
    assert empty.id in related_ids
    assert null_scalar.id in related_ids
    legacy_related = QueryFilterBuilder('tags.name NOT IN ["excluded"]').filter_query(
        select(RecipeModel.id), RecipeModel
    )
    assert related_ids == legacy_ids(tortoise_recipe_db, legacy_related)

    scalar = await repo.page_all(PaginationQuery(per_page=-1, query_filter="rating NOT IN [5]", order_by="name"))
    scalar_ids = {item.id for item in scalar.items}
    assert numeric_scalar.id not in scalar_ids
    # SQL NOT IN does not match NULL, unlike related anti-existence which keeps
    # a parent with no related row matching the excluded value.
    assert null_scalar.id not in scalar_ids
    legacy_scalar = QueryFilterBuilder("rating NOT IN [5]").filter_query(select(RecipeModel.id), RecipeModel)
    assert scalar_ids == legacy_ids(tortoise_recipe_db, legacy_scalar)

    related_not_equal = await repo.page_all(
        PaginationQuery(per_page=-1, query_filter='tags.name <> "excluded"', order_by="name")
    )
    assert {item.id for item in related_not_equal.items} == {matching.id, nonmatching.id}
    legacy_not_equal = QueryFilterBuilder('tags.name <> "excluded"').filter_query(select(RecipeModel.id), RecipeModel)
    assert {item.id for item in related_not_equal.items} == legacy_ids(tortoise_recipe_db, legacy_not_equal)

    scalar_not_equal = await repo.page_all(PaginationQuery(per_page=-1, query_filter="rating <> 5", order_by="name"))
    assert null_scalar.id not in {item.id for item in scalar_not_equal.items}
    legacy_scalar_not_equal = QueryFilterBuilder("rating <> 5").filter_query(select(RecipeModel.id), RecipeModel)
    assert {item.id for item in scalar_not_equal.items} == legacy_ids(tortoise_recipe_db, legacy_scalar_not_equal)


@pytest.mark.asyncio
async def test_contains_all_matches_separate_rows_single_value_and_empty_list(tortoise_recipe_db):
    group = await create_group()
    alpha = await Tag.create(id=uuid4(), group=group, name="alpha", slug="alpha")
    beta = await Tag.create(id=uuid4(), group=group, name="beta", slug="beta")
    only_alpha = await create_recipe(group, "alpha-only", [alpha])
    both = await create_recipe(group, "both", [alpha, beta])
    await create_recipe(group, "none")
    repo = AsyncRepository(Recipe, RecipeResult, group_id=group.id)

    all_values = await repo.page_all(
        PaginationQuery(per_page=-1, query_filter="tags.name CONTAINS ALL [alpha, beta]", order_by="name")
    )
    assert [item.id for item in all_values.items] == [both.id]
    legacy_all = QueryFilterBuilder("tags.name CONTAINS ALL [alpha, beta]").filter_query(
        select(RecipeModel.id), RecipeModel
    )
    assert {item.id for item in all_values.items} == legacy_ids(tortoise_recipe_db, legacy_all)

    one_value = await repo.page_all(
        PaginationQuery(per_page=-1, query_filter="tags.name CONTAINS ALL [alpha]", order_by="name")
    )
    assert {item.id for item in one_value.items} == {only_alpha.id, both.id}
    legacy_one = QueryFilterBuilder("tags.name CONTAINS ALL [alpha]").filter_query(select(RecipeModel.id), RecipeModel)
    assert {item.id for item in one_value.items} == legacy_ids(tortoise_recipe_db, legacy_one)

    # The unchanged parser represents [] as [""], so CONTAINS ALL [] means
    # “has a related empty-string value” rather than an empty conjunction.
    legacy_query = QueryFilterBuilder("tags.name CONTAINS ALL []").filter_query(select(RecipeModel.id), RecipeModel)
    empty_values = await repo.page_all(
        PaginationQuery(per_page=-1, query_filter="tags.name CONTAINS ALL []", order_by="name")
    )
    assert empty_values.items == []
    assert {item.id for item in empty_values.items} == legacy_ids(tortoise_recipe_db, legacy_query)


@pytest.mark.asyncio
async def test_like_wildcards_and_case_insensitivity_match_legacy(tortoise_recipe_db):
    group = await create_group()
    expected = await create_recipe(group, "Test Unit 1")
    wildcard = await create_recipe(group, "test uXit 2")
    await create_recipe(group, "other")
    repo = AsyncRepository(Recipe, RecipeResult, group_id=group.id)
    query_filter = 'name LIKE "test u_it%"'
    result = await repo.page_all(PaginationQuery(per_page=-1, query_filter=query_filter))
    assert {item.id for item in result.items} == {expected.id, wildcard.id}
    legacy_query = QueryFilterBuilder(query_filter).filter_query(select(RecipeModel.id), RecipeModel)
    assert {item.id for item in result.items} == legacy_ids(tortoise_recipe_db, legacy_query)


@pytest.mark.asyncio
async def test_nested_filter_groups_keep_and_or_precedence(tortoise_recipe_db):
    group = await create_group()
    first = await create_recipe(group, "combo first", rating=1)
    await create_recipe(group, "combo second", rating=2)
    third = await create_recipe(group, "combo third", rating=3)
    await create_recipe(group, "other first", rating=1)
    repo = AsyncRepository(Recipe, RecipeResult, group_id=group.id)
    query_filter = 'name LIKE "combo%" AND (rating = 1 OR rating = 3)'
    result = await repo.page_all(PaginationQuery(per_page=-1, query_filter=query_filter, order_by="name"))
    assert {item.id for item in result.items} == {first.id, third.id}
    legacy = QueryFilterBuilder(query_filter).filter_query(select(RecipeModel.id), RecipeModel)
    assert {item.id for item in result.items} == legacy_ids(tortoise_recipe_db, legacy)


@pytest.mark.asyncio
async def test_to_one_sort_null_position_matches_legacy(tortoise_recipe_db):
    group = await create_group()
    named_user = await User.create(id=uuid4(), group=group, full_name="Visible")
    with_user = await Recipe.create(id=uuid4(), group=group, user=named_user, name="named", name_normalized="named")
    without_user = await create_recipe(group, "anonymous")
    repo = AsyncRepository(Recipe, RecipeResult, group_id=group.id)
    result = await repo.page_all(
        PaginationQuery(
            per_page=-1,
            order_by="user.full_name",
            order_direction=OrderDirection.asc,
            order_by_null_position=OrderByNullPosition.first,
        )
    )
    assert [item.id for item in result.items] == [without_user.id, with_user.id]
    legacy = select(RecipeModel.id).order_by(
        QueryFilterBuilder.get_order_attr("user.full_name", RecipeModel, descending=False).asc().nulls_first()
    )
    assert [item.id for item in result.items] == legacy_ids_ordered(tortoise_recipe_db, legacy)


@pytest.mark.asyncio
async def test_to_many_sort_aggregates_nulls_counts_and_page_size(tortoise_recipe_db):
    group = await create_group()
    tags = [await Tag.create(id=uuid4(), group=group, name=name, slug=name) for name in ("a", "b", "c", "d", "e", "f")]
    recipe_ac = await create_recipe(group, "ac", [tags[0], tags[2]])
    recipe_bd = await create_recipe(group, "bd", [tags[1], tags[3]])
    recipe_untagged = await create_recipe(group, "untagged")
    # Three joined rows per root record must not consume three page slots.
    page_group = await create_group("stage7-page")
    page_tags = [await Tag.create(id=uuid4(), group=page_group, name=f"page-{i}", slug=f"page-{i}") for i in range(3)]
    for index in range(5):
        await create_recipe(page_group, f"page-recipe-{index}", page_tags)

    repo = AsyncRepository(Recipe, RecipeResult, group_id=group.id)
    ascending = await repo.page_all(
        PaginationQuery(
            per_page=-1,
            order_by="tags.name",
            order_direction=OrderDirection.asc,
            order_by_null_position=OrderByNullPosition.last,
        )
    )
    assert [item.id for item in ascending.items] == [recipe_ac.id, recipe_bd.id, recipe_untagged.id]
    # The focused Tortoise assertion above checks the MIN aggregate behavior;
    # legacy's aggregate order expression is compared explicitly below.
    from mealie.services.query_filter.builder import QueryFilterBuilder

    expected_ascending = select(RecipeModel.id).order_by(
        QueryFilterBuilder.get_order_attr("tags.name", RecipeModel, descending=False).asc().nulls_last()
    )
    legacy_ordered_ids = legacy_ids_ordered(tortoise_recipe_db, expected_ascending)
    selected_ids = {recipe_ac.id, recipe_bd.id, recipe_untagged.id}
    assert [item.id for item in ascending.items] == [
        item_id for item_id in legacy_ordered_ids if item_id in selected_ids
    ]

    descending = await repo.page_all(
        PaginationQuery(
            per_page=-1,
            order_by="tags.name",
            order_direction=OrderDirection.desc,
            order_by_null_position=OrderByNullPosition.last,
        )
    )
    assert [item.id for item in descending.items] == [recipe_bd.id, recipe_ac.id, recipe_untagged.id]
    expected_descending = select(RecipeModel.id).order_by(
        QueryFilterBuilder.get_order_attr("tags.name", RecipeModel, descending=True).desc().nulls_last()
    )
    legacy_ordered_ids = legacy_ids_ordered(tortoise_recipe_db, expected_descending)
    assert [item_id for item_id in legacy_ordered_ids if item_id in selected_ids] == [
        item.id for item in descending.items
    ]

    page_repo = AsyncRepository(Recipe, RecipeResult, group_id=page_group.id)
    first_page = await page_repo.page_all(
        PaginationQuery(page=1, per_page=5, order_by="tags.name", order_direction=OrderDirection.asc)
    )
    assert first_page.total == 5
    assert len(first_page.items) == 5
    assert len({item.id for item in first_page.items}) == 5


def legacy_ids_ordered(db_path, query) -> list[UUID]:
    connection = sqlite3.connect(db_path)
    try:
        sql = str(query.compile(compile_kwargs={"literal_binds": True}))
        return [UUID(row[0]) for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()
