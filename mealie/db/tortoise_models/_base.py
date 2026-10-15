from uuid import UUID

from tortoise import fields
from tortoise.models import Model


class MealieUUIDField(fields.UUIDField):
    """UUID mapping compatible with SQLAlchemy's compact SQLite GUID columns."""

    SQL_TYPE = "CHAR(32)"

    class _db_postgres:
        SQL_TYPE = "UUID"

    def to_db_value(self, value, instance):
        if value is None:
            return None
        uuid_value = value if isinstance(value, UUID) else UUID(str(value))
        if self.model._meta.db.capabilities.dialect == "sqlite":
            return uuid_value.hex
        return str(uuid_value)

    def to_python_value(self, value):
        if value is None or isinstance(value, UUID):
            return value
        return UUID(str(value))


class TortoiseBaseModel(Model):
    """Shared database columns matching the legacy SQLAlchemy base."""

    id = MealieUUIDField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        abstract = True

