import json
from importlib import import_module

from tortoise import Model, fields

from mealie.core.config import get_app_settings
from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._model_utils.datetime import NaiveDateTime
from mealie.db.tortoise_config import TORTOISE_MODEL_MODULES
from mealie.services.backups_v2.alchemy_exporter import AlchemyExporter
from tests.utils.alembic_reader import alembic_versions


def test_alchemy_exporter():
    settings = get_app_settings()
    exporter = AlchemyExporter(settings.DB_URL)
    data = exporter.dump()

    assert data["alembic_version"] == alembic_versions()
    assert json.dumps(data, indent=4)  # Make sure data is json-serializable

    exporter.engine.dispose()


def test_every_datetime_column_survives_a_backup():
    """Restores rebuild datetimes by column name, so an unregistered one comes back as a string.

    The failure is silent at backup time and only shows up on restore, so this asserts the two stay
    in step rather than waiting for someone to notice a broken restore.
    """
    datetime_columns = {
        column.name
        for table in SqlAlchemyBase.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, NaiveDateTime)
    }
    # Include converted domains without opening a database context. Their field
    # metadata is available at import time, including explicit column aliases.
    for module_name in TORTOISE_MODEL_MODULES:
        for model in vars(import_module(module_name)).values():
            if not isinstance(model, type) or not issubclass(model, Model) or model._meta.abstract:
                continue
            datetime_columns.update(
                field.source_field or name
                for name, field in model._meta.fields_map.items()
                if isinstance(field, fields.DatetimeField)
            )

    unregistered = datetime_columns - AlchemyExporter.look_for_datetime
    assert not unregistered, (
        f"datetime columns missing from AlchemyExporter.look_for_datetime: {sorted(unregistered)}. "
        "Add them, or they will restore as strings."
    )
