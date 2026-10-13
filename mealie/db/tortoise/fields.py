"""Tortoise fields that read and write values in the same format as the SQLAlchemy types.

Stage S1 of REWRITE_PLAN.md: both ORMs share one database until the end of the migration.
- GUID: native UUID on PostgreSQL, 32-character hex without hyphens on SQLite (see
  mealie/db/models/_model_utils/guid.py).
- NaiveDateTime: stored naive in UTC, returned with UTC attached (see
  mealie/db/models/_model_utils/datetime.py).
"""

import datetime
import uuid
from typing import Any

from tortoise.fields.base import Field
from tortoise.fields.data import DatetimeField

from mealie.core.config import get_app_settings

# format SQLAlchemy's SQLite dialect uses for DATETIME columns
SQLITE_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def is_postgres() -> bool:
    return get_app_settings().DB_ENGINE == "postgres"


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def utc_today() -> datetime.date:
    return utc_now().date()


def utc_time() -> datetime.time:
    return utc_now().time()


class GUIDField(Field[uuid.UUID], uuid.UUID):  # type: ignore[misc]
    SQL_TYPE = "CHAR(32)"

    class _db_postgres:
        SQL_TYPE = "UUID"

    def __init__(self, **kwargs: Any) -> None:
        if kwargs.get("primary_key") and "default" not in kwargs:
            kwargs["default"] = uuid.uuid4
        super().__init__(**kwargs)

    def to_db_value(self, value: Any, instance: Any) -> Any:
        if value is None:
            return None
        value = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value) if is_postgres() else value.hex

    def to_python_value(self, value: Any) -> uuid.UUID | None:
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class UTCDatetimeField(DatetimeField):
    SQL_TYPE = "TIMESTAMP"

    class _db_postgres:
        SQL_TYPE = "TIMESTAMP"

    def to_db_value(self, value: Any, instance: Any) -> Any:
        if hasattr(instance, "_saved_in_db") and (
            self.auto_now or (self.auto_now_add and getattr(instance, self.model_field_name) is None)
        ):
            value = utc_now()
            setattr(instance, self.model_field_name, value)
        if not isinstance(value, datetime.datetime):
            return value
        if value.tzinfo is not None:
            value = value.astimezone(datetime.UTC).replace(tzinfo=None)
        return value if is_postgres() else value.strftime(SQLITE_DATETIME_FORMAT)

    def to_python_value(self, value: Any) -> datetime.datetime | None:
        value = super().to_python_value(value)
        if value is None:
            return None
        return value.replace(tzinfo=datetime.UTC) if value.tzinfo is None else value.astimezone(datetime.UTC)
