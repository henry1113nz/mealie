from datetime import UTC, date, datetime, time
from typing import Any

from tortoise import Model, fields
from tortoise.fields import DatetimeField


def get_utc_now() -> datetime:
    return datetime.now(UTC)


def get_utc_today() -> date:
    return datetime.now(UTC).date()


class NaiveDateTime(DatetimeField):
    """UTC datetime field; Tortoise handles backend-specific storage and conversion."""


class DateField(fields.DateField):
    """Accept datetime inputs as calendar dates, as the API historically has."""

    def to_python_value(self, value: Any) -> date | None:
        return value.date() if isinstance(value, datetime) else super().to_python_value(value)

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> date | None:
        return super().to_db_value(self.to_python_value(value), instance)


class TimeField(fields.Field[time]):
    """UTC wall-clock time with explicit SQLite parameter serialization."""

    field_type = time
    SQL_TYPE = "TIME"

    def to_python_value(self, value: Any) -> time | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            value = value.astimezone(UTC).time()
        elif isinstance(value, str):
            value = time.fromisoformat(value)
        return value.replace(tzinfo=None)

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> time | str | None:
        value = self.to_python_value(value)
        self.validate(value)
        if value is not None and instance._meta.db.capabilities.dialect == "sqlite":
            return value.isoformat()
        return value
