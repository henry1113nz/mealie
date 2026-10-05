import json

from tortoise import Tortoise, fields

from mealie.core.config import get_app_settings
from mealie.services.backups_v2.alchemy_exporter import AlchemyExporter
from tests.fixtures.fixture_database import run_db
from tests.utils.alembic_reader import alembic_versions


def test_alchemy_exporter():
    settings = get_app_settings()
    exporter = AlchemyExporter(settings.DB_URL)
    data = run_db(exporter.dump())

    assert data["alembic_version"] == alembic_versions()
    assert json.dumps(data, indent=4)  # Make sure data is json-serializable


def test_every_datetime_column_survives_a_backup():
    """Restores rebuild datetimes by column name, so an unregistered one comes back as a string.

    The failure is silent at backup time and only shows up on restore, so this asserts the two stay
    in step rather than waiting for someone to notice a broken restore.
    """
    datetime_columns = {
        model._meta.fields_db_projection[name]
        for model in Tortoise.apps["models"].values()
        if model.__module__.startswith("mealie.")
        for name, field in model._meta.fields_map.items()
        if name in model._meta.db_fields and isinstance(field, fields.DatetimeField)
    }

    unregistered = datetime_columns - AlchemyExporter.look_for_datetime
    assert not unregistered, (
        f"datetime columns missing from AlchemyExporter.look_for_datetime: {sorted(unregistered)}. "
        "Add them, or they will restore as strings."
    )
