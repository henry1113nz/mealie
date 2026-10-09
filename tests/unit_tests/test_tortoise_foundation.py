import pytest
from tortoise import Tortoise

from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.tortoise import (
    TORTOISE_ORM,
    IntIdModel,
    TortoiseBase,
    UUIDIdModel,
    close_tortoise,
    get_db_url,
    get_tortoise_config,
    init_tortoise,
)


def test_tortoise_config():
    config = get_tortoise_config()
    assert "connections" in config
    assert "default" in config["connections"]
    assert "apps" in config
    assert "models" in config["apps"]
    assert "models" in config["apps"]["models"]
    assert "mealie.db.tortoise.models" in config["apps"]["models"]["models"]

    custom_url = "sqlite:////tmp/test.db"
    custom_config = get_tortoise_config(db_url=custom_url)
    assert custom_config["connections"]["default"] == custom_url


def test_tortoise_orm_dict_exported():
    assert isinstance(TORTOISE_ORM, dict)
    assert "connections" in TORTOISE_ORM


def test_tortoise_base_normalize():
    test_str = "Crème Brûlée & Co.! (Special #1)"
    expected = SqlAlchemyBase.normalize(test_str)
    actual = TortoiseBase.normalize(test_str)
    assert actual == expected


def test_tortoise_base_models_abstract():
    assert TortoiseBase._meta.abstract is True
    assert IntIdModel._meta.abstract is True
    assert UUIDIdModel._meta.abstract is True


@pytest.mark.asyncio
async def test_tortoise_lifecycle():
    # Calling init_tortoise when already inited should be safe and idempotent
    await init_tortoise()
    assert Tortoise._inited is True
