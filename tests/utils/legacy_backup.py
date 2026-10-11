"""Prepare historical backup fixtures; this is never imported by production code."""

import datetime
import json
import os
import tempfile
import uuid
from logging import Logger
from os import path
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import patch
from zipfile import ZipFile

from alembic import command
from alembic.config import Config
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import Connection, ForeignKey, MetaData, Table, create_engine, insert, text
from sqlalchemy.engine import base
from sqlalchemy.orm import sessionmaker

from mealie.core.config import get_app_dirs, get_app_settings
from mealie.core.settings.db_providers import SQLiteProvider
from mealie.services._base_service import BaseService
from mealie.services.backups_v2.backup_file import BackupFile
from mealie.services.backups_v2.tortoise_exporter import TortoiseExporter
from tests.fixtures.legacy_models._model_utils.guid import GUID
from tests.utils.alembic_reader import ALEMBIC_DIR
from tests.utils.async_database import run_async
from tests.utils.legacy_backup_fixes import fix_migration_data


class ForeignKeyDisabler:
    def __init__(self, connection: Connection, dialect_name: str, *, logger: Logger | None = None):
        self.connection = connection
        self.is_postgres = dialect_name == "postgresql"
        self.logger = logger

        self._initial_fk_state: str | None = None

    def __enter__(self):
        if self.is_postgres:
            self._initial_fk_state = self.connection.execute(text("SHOW session_replication_role;")).scalar()
            self.connection.execute(text("SET session_replication_role = 'replica';"))
        else:
            self._initial_fk_state = self.connection.execute(text("PRAGMA foreign_keys;")).scalar()
            self.connection.execute(text("PRAGMA foreign_keys = OFF;"))

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.is_postgres:
                initial_state = self._initial_fk_state or "origin"
                self.connection.execute(text(f"SET session_replication_role = '{initial_state}';"))
            else:
                initial_state = self._initial_fk_state or "ON"
                self.connection.execute(text(f"PRAGMA foreign_keys = {initial_state};"))
        except Exception:
            if self.logger:
                self.logger.exception("Error when re-enabling foreign keys")
            raise


class AlchemyExporter(BaseService):
    connection_str: str
    engine: base.Engine
    meta: MetaData

    look_for_datetime = {
        "created_at",
        "update_at",
        "date_updated",
        "timestamp",
        "expires_at",
        "locked_at",
        "last_made",
        "completed_date",
        "tokens_valid_after",
    }
    """Column names restored back into datetimes. Anything stored as a `NaiveDateTime` and missing
    here comes back from a backup as a string; `test_every_datetime_column_survives_a_backup` guards
    against forgetting to add one."""
    look_for_date = {"date_added", "date"}
    look_for_time = {"scheduled_time"}

    class DateTimeParser(BaseModel):
        date: datetime.date | None = None
        dt: datetime.datetime | None = None
        time: datetime.time | None = None

    def __init__(self, connection_str: str) -> None:
        super().__init__()

        self.connection_str = connection_str
        self.engine = create_engine(connection_str)
        self.meta = MetaData()
        self.session_maker = sessionmaker(bind=self.engine)

    @staticmethod
    def is_uuid(value: Any) -> bool:
        try:
            uuid.UUID(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_valid_foreign_key(db_dump: dict[str, list[dict]], fk: ForeignKey, fk_value: Any) -> bool:
        if not fk_value:
            return True

        foreign_table_name = fk.column.table.name
        foreign_field_name = fk.column.name

        for row in db_dump.get(foreign_table_name, []):
            if row[foreign_field_name] == fk_value:
                return True

        return False

    def convert_types(self, data: dict) -> dict:
        """
        walks the dictionary to restore all things that look like string representations of their complex types
        used in the context of reading a json file into a database via SQLAlchemy.
        """
        for key, value in data.items():
            if isinstance(value, dict):
                data = self.convert_types(value)
            elif isinstance(value, list):  # assume that this is a list of dictionaries
                data[key] = [self.convert_types(item) for item in value]
            elif isinstance(value, str):
                if self.is_uuid(value):
                    # convert the data to the current database's native GUID type
                    data[key] = GUID.convert_value_to_guid(value, self.engine.dialect)
                if key in self.look_for_datetime:
                    data[key] = self.DateTimeParser(dt=value).dt
                if key in self.look_for_date:
                    data[key] = self.DateTimeParser(date=value).date
                if key in self.look_for_time:
                    data[key] = self.DateTimeParser(time=value).time
        return data

    def clean_rows(self, db_dump: dict[str, list[dict]], table: Table, rows: list[dict]) -> list[dict]:
        """
        Checks rows against foreign key restraints and removes any rows that would violate them
        """

        fks = table.foreign_keys

        valid_rows = []
        for row in rows:
            is_valid_row = True
            for fk in fks:
                fk_value = row.get(fk.parent.name)
                if self.is_valid_foreign_key(db_dump, fk, row.get(fk.parent.name)):
                    continue

                is_valid_row = False
                self.logger.warning(
                    f"Removing row from table {table.name} because of invalid foreign key {fk.parent.name}: {fk_value}"
                )
                self.logger.warning(f"Row: {row}")
                break

            if is_valid_row:
                valid_rows.append(row)

        return valid_rows

    def dump_schema(self) -> dict:
        """
        Returns the schema of the SQLAlchemy database as a python dictionary. This dictionary is wrapped by
        jsonable_encoder to ensure that the object can be converted to a json string.
        """
        with self.engine.connect() as connection:
            self.meta.reflect(bind=self.engine)

            all_tables = self.meta.tables.values()

            results = {
                **{table.name: [] for table in all_tables},
                "alembic_version": [
                    dict(row) for row in connection.execute(text("SELECT * FROM alembic_version")).mappings()
                ],
            }

            return jsonable_encoder(results)

    def dump(self) -> dict[str, list[dict]]:
        """
        Returns the entire SQLAlchemy database as a python dictionary. This dictionary is wrapped by
        jsonable_encoder to ensure that the object can be converted to a json string.
        """

        # run database fixes first so we aren't backing up bad data
        with self.session_maker() as session:
            try:
                fix_migration_data(session)
            except Exception:
                self.logger.error("Error fixing migration data during export; continuing anyway")

        with self.engine.connect() as connection:
            self.meta.reflect(bind=self.engine)  #  http://docs.sqlalchemy.org/en/rel_0_9/core/reflection.html

            result = {
                table.name: [dict(row) for row in connection.execute(table.select()).mappings()]
                for table in self.meta.tables.values()
            }

        return jsonable_encoder(result)

    def restore(self, db_dump: dict) -> None:
        # setup alembic to run migrations up the version of the backup
        alembic_data = db_dump["alembic_version"]
        alembic_version = alembic_data[0]["version_num"]

        alembic_cfg_path = os.getenv("ALEMBIC_CONFIG_FILE", default=str(ALEMBIC_DIR / "alembic.ini"))

        if not path.isfile(alembic_cfg_path):
            raise Exception("Provided alembic config path doesn't exist")

        alembic_cfg = Config(alembic_cfg_path)
        command.upgrade(alembic_cfg, alembic_version)

        del db_dump["alembic_version"]
        """Restores all data from dictionary into the database"""
        with self.engine.begin() as connection:
            with ForeignKeyDisabler(connection, self.engine.dialect.name, logger=self.logger):
                data = self.convert_types(db_dump)

                self.meta.reflect(bind=self.engine)
                for table_name, rows in data.items():
                    if not rows:
                        continue
                    table = self.meta.tables[table_name]
                    rows = self.clean_rows(db_dump, table, rows)

                    connection.execute(table.delete())
                    connection.execute(insert(table), rows)
                if self.engine.dialect.name == "postgresql":
                    # Restore postgres sequence numbers
                    sequences = [
                        ("api_extras_id_seq", "api_extras"),
                        ("group_meal_plans_id_seq", "group_meal_plans"),
                        ("ingredient_food_extras_id_seq", "ingredient_food_extras"),
                        ("invite_tokens_id_seq", "invite_tokens"),
                        ("long_live_tokens_id_seq", "long_live_tokens"),
                        ("notes_id_seq", "notes"),
                        ("password_reset_tokens_id_seq", "password_reset_tokens"),
                        ("recipe_assets_id_seq", "recipe_assets"),
                        ("recipe_ingredient_ref_link_id_seq", "recipe_ingredient_ref_link"),
                        ("recipe_nutrition_id_seq", "recipe_nutrition"),
                        ("recipe_settings_id_seq", "recipe_settings"),
                        ("recipes_ingredients_id_seq", "recipes_ingredients"),
                        ("server_tasks_id_seq", "server_tasks"),
                        ("shopping_list_extras_id_seq", "shopping_list_extras"),
                        ("shopping_list_item_extras_id_seq", "shopping_list_item_extras"),
                    ]

                    sql = "\n".join(
                        [f"SELECT SETVAL('{seq}', (SELECT MAX(id) FROM {table}));" for seq, table in sequences]
                    )
                    connection.execute(text(dedent(sql)))

        # Dispose this exporter's engine to release connections back to the database.
        # This releases the legacy pool before database initialization needs connections.
        self.engine.dispose()

        # Historical migrations exist solely to prepare existing fixture archives.
        command.upgrade(alembic_cfg, "head")
        with self.session_maker() as session:
            fix_migration_data(session)
        self.meta.clear()


def aerich_versions() -> list[dict[str, str]]:
    """Read the native migration's expected version, independently of the dump."""
    from mealie.db.init_db import MIGRATIONS_DIR

    return [{"version_num": migration.name} for migration in sorted((MIGRATIONS_DIR / "models").glob("[0-9]*.py"))]


def prepare_legacy_backup(backup_path: Path) -> Path:
    """Keep old archive rows and migration assertions while updating test setup.

    Production deliberately rejects old Alembic archives. Only the pre-existing
    migration regression fixtures are upgraded using the archived test history.
    The resulting archive exercises the same native restore path as new backups.
    """
    settings = get_app_settings()
    with tempfile.TemporaryDirectory() as directory:
        provider = SQLiteProvider(data_dir=Path(directory))
        fixture_settings = settings.model_copy(update={"DB_PROVIDER": provider})
        exporter = AlchemyExporter(fixture_settings.DB_URL)
        try:
            with patch("mealie.core.config.get_app_settings", return_value=fixture_settings):
                with BackupFile(backup_path) as backup:
                    exporter.restore(backup.read_tables())
                data = exporter.dump()
        finally:
            exporter.engine.dispose()

    schema = run_async(TortoiseExporter().dump_schema())
    data.pop("alembic_version", None)
    native_data = {name: data.get(name, []) for name in schema}
    native_data["aerich"] = schema["aerich"]
    output = get_app_dirs().DATA_DIR / f"native-{backup_path.name}"
    temporary_output = output.with_suffix(".tmp.zip")
    with ZipFile(backup_path) as source, ZipFile(temporary_output, "w") as destination:
        for entry in source.infolist():
            if entry.filename == "database.json":
                destination.writestr(entry, json.dumps(native_data))
            else:
                destination.writestr(entry, source.read(entry))
    temporary_output.replace(output)
    return output
