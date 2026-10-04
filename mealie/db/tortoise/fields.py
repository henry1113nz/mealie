"""Tortoise field types that store values exactly as the SQLAlchemy models did.

Both ORMs read and write the same tables while the backend is being migrated, so the
on-disk formats must match:

* GUIDs are a native UUID on PostgreSQL and a 32 character hex string (no hyphens) on SQLite.
* Datetimes are stored naive and in UTC, and come back as UTC-aware datetimes.
"""

import datetime
import uuid
from typing import Any

from tortoise.fields.base import Field
from tortoise.fields.data import DatetimeField

from mealie.core.config import get_app_settings

# SQLAlchemy's SQLite dialect stores datetimes in this format; keeping it means string
# comparison and ordering in SQLite behave the same for rows written by either ORM.
_SQLITE_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def _is_postgres() -> bool:
    return get_app_settings().DB_ENGINE == "postgres"


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
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return str(value) if _is_postgres() else f"{value.int:032x}"

    def to_python_value(self, value: Any) -> uuid.UUID | None:
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class NaiveUTCDatetimeField(DatetimeField):
    """Mirrors mealie.db.models._model_utils.datetime.NaiveDateTime."""

    SQL_TYPE = "TIMESTAMP"

    class _db_postgres:
        SQL_TYPE = "TIMESTAMP"

    def to_db_value(self, value: Any, instance: Any) -> Any:
        if hasattr(instance, "_saved_in_db"):
            # auto_now / auto_now_add handling from the parent class
            if self.auto_now or (self.auto_now_add and getattr(instance, self.model_field_name) is None):
                value = datetime.datetime.now(datetime.UTC)
                setattr(instance, self.model_field_name, value)
        if value is None or not isinstance(value, datetime.datetime):
            return value
        if value.tzinfo is not None:
            value = value.astimezone(datetime.UTC).replace(tzinfo=None)
        return value if _is_postgres() else value.strftime(_SQLITE_DATETIME_FORMAT)

    def to_python_value(self, value: Any) -> datetime.datetime | None:
        value = super().to_python_value(value)
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.UTC)
        return value.astimezone(datetime.UTC)


def get_utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def get_utc_today() -> datetime.date:
    return datetime.datetime.now(datetime.UTC).date()


def get_utc_time() -> datetime.time:
    return datetime.datetime.now(datetime.UTC).time()
