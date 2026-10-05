from slugify import slugify

from mealie.repos.repository_factory import AllRepositories
from tests.fixtures.fixture_database import run_db
from tests.utils.factories import random_int, random_string


def test_create_group_resolve_similar_names(unfiltered_database: AllRepositories):
    base_group_name = random_string()
    groups = run_db(unfiltered_database.groups.create_many({"name": base_group_name} for _ in range(random_int(3, 10))))

    seen_names = set()
    seen_slugs = set()
    for group in groups:
        assert group.name not in seen_names
        assert group.slug not in seen_slugs
        seen_names.add(group.name)
        seen_slugs.add(group.slug)

        assert base_group_name in group.name


def test_group_get_by_slug_or_id(unfiltered_database: AllRepositories):
    groups = [run_db(unfiltered_database.groups.create({"name": random_string()})) for _ in range(random_int(3, 10))]
    for group in groups:
        assert run_db(unfiltered_database.groups.get_by_slug_or_id(group.id)) == group
        assert run_db(unfiltered_database.groups.get_by_slug_or_id(group.slug)) == group


def test_update_group_updates_slug(unfiltered_database: AllRepositories):
    group = run_db(unfiltered_database.groups.create({"name": random_string()}))
    assert group.slug == slugify(group.name)

    new_name = random_string()
    group = run_db(unfiltered_database.groups.update(group.id, {"name": new_name}))
    assert group.slug == slugify(new_name)
