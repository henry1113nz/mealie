"""Stage S2 acceptance (REWRITE_PLAN.md): implicit SQLAlchemy behaviour, done explicitly for
Tortoise, matches SQLAlchemy for one model of each kind.

- cascade and nulling on delete: MultiPurposeLabel
- one-to-one nested write: GroupEventNotifierModel.options
- scoping through an association proxy: RecipeModel.household_id (really user.household_id)
"""

import sqlalchemy as sa
from fastapi.testclient import TestClient

from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.tortoise import models as tm
from mealie.db.tortoise.behaviour import delete_with_relations, scope_filter, write_children
from mealie.schema.labels.multi_purpose_label import MultiPurposeLabelSave
from mealie.schema.recipe import Recipe
from mealie.schema.recipe.recipe_ingredient import SaveIngredientFood
from tests.utils import api_routes
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser


def _run(api_client: TestClient, fn, *args):
    return api_client.portal.call(fn, *args)  # type: ignore[union-attr]


def test_label_delete_matches_sqlalchemy(api_client: TestClient, unique_user: TestUser):
    repos = unique_user.repos
    labels = [
        repos.group_multi_purpose_labels.create(
            MultiPurposeLabelSave(name=random_string(), group_id=unique_user.group_id)
        )
        for _ in range(2)
    ]
    # creating a list adds a label setting for every existing label
    response = api_client.post(
        api_routes.households_shopping_lists, json={"name": random_string()}, headers=unique_user.token
    )
    assert response.status_code == 201
    list_id = response.json()["id"]
    foods = [
        repos.ingredient_foods.create(
            SaveIngredientFood(name=random_string(), group_id=unique_user.group_id, label_id=label.id)
        )
        for label in labels
    ]

    async def label_state(label_id):
        settings = await tm.ShoppingListMultiPurposeLabel.filter(label_id=label_id).count()
        food = await tm.IngredientFoodModel.get(id=foods[[lbl.id for lbl in labels].index(label_id)].id)
        return settings, food.label_id

    for label in labels:
        assert _run(api_client, label_state, label.id) == (1, label.id)

    repos.group_multi_purpose_labels.delete(labels[0].id)

    async def delete_with_tortoise(label_id):
        await delete_with_relations(await tm.MultiPurposeLabel.get(id=label_id))

    _run(api_client, delete_with_tortoise, labels[1].id)

    # same outcome for both: settings deleted, foods kept without a label, list untouched
    assert _run(api_client, label_state, labels[0].id) == (0, None)
    assert _run(api_client, label_state, labels[1].id) == (0, None)

    async def list_exists():
        return await tm.ShoppingList.filter(id=list_id).exists()

    assert _run(api_client, list_exists)


def test_notifier_options_one_to_one_write(api_client: TestClient, unique_user: TestUser):
    household = unique_user.repos.households.get_one(unique_user.household_id)
    assert household

    async def create():
        notifier = await tm.GroupEventNotifierModel.create(
            name=random_string(),
            apprise_url="json://localhost",
            enabled=True,
            group_id=unique_user.group_id,
            household_id=household.id,
        )
        await write_children(notifier, {"options": {"recipe_created": True}})
        return notifier.id

    notifier_id = _run(api_client, create)
    read = unique_user.repos.group_event_notifier.get_one(notifier_id)
    assert read and read.options.recipe_created and not read.options.tag_created

    async def update():
        notifier = await tm.GroupEventNotifierModel.get(id=notifier_id)
        await write_children(notifier, {"options": {"recipe_created": False, "tag_created": True}})
        return await tm.GroupEventNotifierOptionsModel.filter(event_notifier_id=notifier_id).count()

    assert _run(api_client, update) == 1  # updated in place, not a second options row
    unique_user.repos.session.expire_all()
    read = unique_user.repos.group_event_notifier.get_one(notifier_id)
    assert read and not read.options.recipe_created and read.options.tag_created


def test_recipe_household_scope_follows_the_proxy(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    for user in (unique_user, h2_user):
        user.repos.recipes.create(Recipe(user_id=user.user_id, group_id=user.group_id, name=random_string()))

    session = unique_user.repos.session
    for user in (unique_user, h2_user):
        expected = set(
            session.execute(sa.select(RecipeModel.id).filter_by(group_id=user.group_id, household_id=user.household_id))
            .scalars()
            .all()
        )

        async def tortoise_ids(group_id=user.group_id, household_id=user.household_id):
            scope = scope_filter(tm.RecipeModel, group_id=group_id, household_id=household_id)
            return set(await tm.RecipeModel.filter(**scope).values_list("id", flat=True))

        assert expected
        assert _run(api_client, tortoise_ids) == expected
