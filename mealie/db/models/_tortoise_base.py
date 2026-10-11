"""Shared model primitives for domains migrated to Tortoise ORM."""

import string
from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID

from text_unidecode import unidecode
from tortoise import Model, fields
from tortoise.fields.data import DatetimeFieldQueryValueType

# Keep storage normalization identical to the existing models and search filters.
_NORMALIZE_PUNCTUATION = string.punctuation.replace("'", "").replace('"', "")
_NORMALIZE_PUNCTUATION_TABLE = str.maketrans(_NORMALIZE_PUNCTUATION, " " * len(_NORMALIZE_PUNCTUATION))


class UUIDField(fields.UUIDField):
    """Use native PostgreSQL UUIDs and SQLite's existing 32-character UUIDs."""

    SQL_TYPE = "CHAR(32)"

    def to_db_value(self, value: Any, instance: type[Model] | Model | None) -> str | None:
        if value is None:
            return None

        identifier = value if isinstance(value, UUID) else UUID(str(value))
        # QuerySet.update passes no instance; the bound field still owns its model.
        model = instance if instance is not None else self.model
        if model._meta.db.capabilities.dialect == "sqlite":
            return identifier.hex
        return str(identifier)


class UnboundedCharField(fields.TextField):
    """Preserve unbounded, indexed strings on SQLite and PostgreSQL.

    Both supported databases permit indexes on unbounded strings. Tortoise's
    standard TextField disallows them for portability to other backends.
    """

    SQL_TYPE = "VARCHAR"
    indexable = True

    def __init__(self, **kwargs: Any) -> None:
        fields.Field.__init__(self, **kwargs)


class UTCDateTimeField(fields.DatetimeField):
    """Store naive UTC timestamps and expose aware UTC datetimes to the API.

    Keeping the existing PostgreSQL column type also allows migrated domains to
    coexist with domains that still use SQLAlchemy during the rewrite.
    """

    class _db_postgres:
        SQL_TYPE = "TIMESTAMP"

    def to_db_value(
        self, value: DatetimeFieldQueryValueType | None, instance: type[Model] | Model
    ) -> DatetimeFieldQueryValueType | None:
        if isinstance(value, datetime):
            value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

        converted = super().to_db_value(value, instance)
        if isinstance(converted, datetime):
            return converted.astimezone(UTC).replace(tzinfo=None)
        return converted

    def to_python_value(self, value: Any) -> datetime | None:
        converted = super().to_python_value(value)
        if converted is None:
            return None
        if converted.tzinfo is None:
            return converted.replace(tzinfo=UTC)
        return converted.astimezone(UTC)


class CalendarDateField(fields.DateField):
    """Preserve SQLAlchemy DATE coercion when callers supply a datetime."""

    skip_to_python_if_native = False

    def to_python_value(self, value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        return super().to_python_value(value)

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> Any:
        converted = self.to_python_value(value)
        self.validate(converted)
        if isinstance(instance, Model):
            setattr(instance, self.model_field_name, converted)
        if converted is not None and instance._meta.db.capabilities.dialect == "sqlite":
            return converted.isoformat()
        return converted


class NaiveTimeField(fields.TimeField):
    """Keep wall-clock values naive, matching the existing SQL TIME columns."""

    skip_to_python_if_native = False

    class _db_postgres:
        SQL_TYPE = "TIME"

    def to_python_value(self, value: Any) -> time | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = time.fromisoformat(value)
        return value.replace(tzinfo=None)

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> Any:
        converted = self.to_python_value(value)
        self.validate(converted)
        if isinstance(instance, Model):
            setattr(instance, self.model_field_name, converted)
        if converted is not None and instance._meta.db.capabilities.dialect == "sqlite":
            return converted.isoformat(timespec="microseconds")
        return converted


class TortoiseBase(Model):
    id: fields.IntField[int] = fields.IntField(primary_key=True)
    created_at: fields.DatetimeField[datetime | None] = UTCDateTimeField(auto_now_add=True, null=True, db_index=True)
    update_at: fields.DatetimeField[datetime | None] = UTCDateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True

    @property
    def updated_at(self) -> datetime | None:
        return self.update_at

    @updated_at.setter
    def updated_at(self, value: datetime | None) -> None:
        self.update_at = value

    @classmethod
    def normalize(cls, value: str) -> str:
        return unidecode(value).translate(_NORMALIZE_PUNCTUATION_TABLE).lower().strip()[:255]
