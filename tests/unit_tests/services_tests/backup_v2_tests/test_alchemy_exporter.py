import json
from importlib import import_module

from tortoise import Model, fields

from mealie.core.config import get_app_settings
from mealie.db.tortoise_config import TORTOISE_MODEL_MODULES
from mealie.services.backups_v2.tortoise_exporter import TortoiseExporter as AlchemyExporter
from tests.utils.async_database import run_async
from tests.utils.legacy_backup import aerich_versions as alembic_versions


def test_alchemy_exporter():
    settings = get_app_settings()
    exporter = AlchemyExporter(settings.DB_URL)
    data = run_async(exporter.dump())

    # Preserve the revision assertion while adapting its database read to Aerich.
    data["alembic_version"] = [{"version_num": row["version"]} for row in data["aerich"]]

    assert data["alembic_version"] == alembic_versions()
    assert json.dumps(data, indent=4)  # Make sure data is json-serializable


def test_every_datetime_column_survives_a_backup():
    """Restores rebuild datetimes by column name, so an unregistered one comes back as a string.

    The failure is silent at backup time and only shows up on restore, so this asserts the two stay
    in step rather than waiting for someone to notice a broken restore.
    """
    datetime_columns: set[str] = set()
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
