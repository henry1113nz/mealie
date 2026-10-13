"""Stage S1 acceptance (REWRITE_PLAN.md): the Tortoise models describe the existing database.

- every Tortoise model can query the database built by the Alembic migrations
- a row written by Tortoise reads back correctly through SQLAlchemy, and the reverse
"""

import inspect

import sqlalchemy as sa
from fastapi.testclient import TestClient

from mealie.db.models.recipe.tag import Tag as SATag
from mealie.db.tortoise import models as tm
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser


def _tortoise_models() -> list[type[tm.Model]]:
    return [
        obj
        for _, obj in inspect.getmembers(tm, inspect.isclass)
        if issubclass(obj, tm.Model) and obj is not tm.Model and obj.__module__ == tm.__name__
    ]


def test_every_tortoise_model_reads_the_migrated_database(api_client: TestClient):
    models = _tortoise_models()
    assert len(models) == 56

    async def query_all() -> list[str]:
        failures = []
        for model in models:
            try:
                await model.all().limit(5)
            except Exception as e:
                failures.append(f"{model.__name__}: {e}")
        return failures

    assert api_client.portal.call(query_all) == []  # type: ignore[union-attr]


def test_rows_round_trip_between_orms(api_client: TestClient, unique_user: TestUser):
    session = unique_user.repos.session
    tortoise_name, sqlalchemy_name = random_string(), random_string()

    async def write_with_tortoise():
        tag = await tm.Tag.create(group_id=unique_user.group_id, name=tortoise_name, slug=tortoise_name)
        return tag.id, tag.created_at

    tag_id, created_at = api_client.portal.call(write_with_tortoise)  # type: ignore[union-attr]
    row = session.execute(sa.select(SATag).where(SATag.id == tag_id)).scalar_one()
    assert row.name == tortoise_name
    assert str(row.group_id) == str(unique_user.group_id)
    assert abs((row.created_at - created_at).total_seconds()) < 1

    sa_tag = SATag(session=session, group_id=unique_user.group_id, name=sqlalchemy_name, slug=sqlalchemy_name)
    session.add(sa_tag)
    session.commit()

    async def read_with_tortoise():
        return await tm.Tag.get(id=sa_tag.id)

    tag = api_client.portal.call(read_with_tortoise)  # type: ignore[union-attr]
    assert tag.name == sqlalchemy_name
    assert str(tag.group_id) == str(unique_user.group_id)
    assert tag.created_at.tzinfo is not None
