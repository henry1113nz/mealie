from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict, UUID4
from tortoise import Tortoise, fields
from tortoise.exceptions import IntegrityError
from tortoise.models import Model

from mealie.repos.tortoise_repository import AsyncRepository
from mealie.db.tortoise_setup import tortoise_close, tortoise_init


class RepositoryGroup(Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    slug = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "stage6_groups"


class RepositoryHousehold(Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255)
    slug = fields.CharField(max_length=255, null=True)
    group: fields.ForeignKeyRelation[RepositoryGroup] = fields.ForeignKeyField(
        "models.RepositoryGroup", related_name="households", on_delete=fields.OnDelete.CASCADE
    )

    class Meta:
        table = "stage6_households"


class RepositoryHouseholdRecord(Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255)
    group: fields.ForeignKeyRelation[RepositoryGroup] = fields.ForeignKeyField(
        "models.RepositoryGroup", related_name="records", on_delete=fields.CASCADE
    )
    household: fields.ForeignKeyRelation[RepositoryHousehold] = fields.ForeignKeyField(
        "models.RepositoryHousehold", related_name="records", on_delete=fields.CASCADE
    )

    class Meta:
        table = "stage6_household_records"


class GroupData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    slug: str | None


class HouseholdData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    group: GroupData


class HouseholdRecordData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    group_id: UUID4
    household_id: UUID4


@pytest.fixture
def sqlite_db(tmp_path):
    """Provide an isolated database and create the models needed by this test file."""
    return str(tmp_path / "async-repository.sqlite3")


@pytest.mark.asyncio
async def test_crud_scope_and_relation_materialization(sqlite_db):
    await _init_test_models(sqlite_db)
    try:
        group_one = await RepositoryGroup.create(id=uuid4(), name="one", slug="one")
        group_two = await RepositoryGroup.create(id=uuid4(), name="two", slug="two")
        household_one = await RepositoryHousehold.create(id=uuid4(), name="home", group=group_one)
        household_two = await RepositoryHousehold.create(id=uuid4(), name="home", group=group_two)

        repo = AsyncRepository(
            RepositoryHousehold, HouseholdData, group_id=group_one.id, related_fields=("group",)
        )
        assert await repo.count() == 1
        assert [item.id for item in await repo.get_all()] == [household_one.id]
        loaded = await repo.get_one(household_one.id)
        assert loaded is not None
        assert loaded.group.id == group_one.id
        assert await repo.get_one(household_two.id) is None

        updated = await repo.update(household_one.id, {"name": "updated"})
        assert updated is not None
        assert updated.name == "updated"
        deleted = await repo.delete(household_one.id)
        assert deleted is not None
        assert await repo.count() == 0
    finally:
        await tortoise_close()


@pytest.mark.asyncio
async def test_create_many_and_failed_write_roll_back(sqlite_db):
    await _init_test_models(sqlite_db)
    try:
        group = await RepositoryGroup.create(id=uuid4(), name="one", slug="one")
        repo = AsyncRepository(
            RepositoryHousehold, HouseholdData, group_id=group.id, related_fields=("group",)
        )
        created = await repo.create_many(
            [
                {"name": "first", "slug": "first", "group_id": group.id},
                {"name": "second", "slug": "second", "group_id": group.id},
            ]
        )
        assert [item.name for item in created] == ["first", "second"]

        with pytest.raises(IntegrityError):
            await repo.create({"name": "invalid", "slug": "invalid", "group_id": uuid4()})

        assert await repo.count() == 2
    finally:
        await tortoise_close()


@pytest.mark.asyncio
async def test_household_scope_isolates_records_within_same_group(sqlite_db):
    await _init_test_models(sqlite_db)
    try:
        group = await RepositoryGroup.create(id=uuid4(), name="shared-group", slug="shared-group")
        household_one = await RepositoryHousehold.create(
            id=uuid4(), name="first household", group=group
        )
        household_two = await RepositoryHousehold.create(
            id=uuid4(), name="second household", group=group
        )
        record_one = await RepositoryHouseholdRecord.create(
            id=uuid4(), name="first record", group=group, household=household_one
        )
        record_two = await RepositoryHouseholdRecord.create(
            id=uuid4(), name="second record", group=group, household=household_two
        )

        repo_one = AsyncRepository(
            RepositoryHouseholdRecord,
            HouseholdRecordData,
            group_id=group.id,
            household_id=household_one.id,
        )
        repo_two = AsyncRepository(
            RepositoryHouseholdRecord,
            HouseholdRecordData,
            group_id=group.id,
            household_id=household_two.id,
        )

        assert [item.id for item in await repo_one.get_all()] == [record_one.id]
        assert await repo_one.get_one(record_two.id) is None
        assert [item.id for item in await repo_two.get_all()] == [record_two.id]
        assert await repo_two.get_one(record_one.id) is None
    finally:
        await tortoise_close()


async def _init_test_models(db_path: str) -> None:
    await Tortoise.init(
        config={
            "connections": {"default": f"sqlite://{db_path}"},
            "apps": {
                "models": {"models": [__name__], "default_connection": "default"},
            },
        }
    )
    await Tortoise.generate_schemas(safe=True)
