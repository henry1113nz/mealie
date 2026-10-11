"""Shared model primitives for domains migrated to Tortoise ORM."""

import string
from datetime import UTC, datetime
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

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> str | None:
        if value is None:
            return None

        identifier = value if isinstance(value, UUID) else UUID(str(value))
        if instance._meta.db.capabilities.dialect == "sqlite":
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
