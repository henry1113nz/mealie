from tortoise import fields
from tortoise.models import Model


class TortoiseBaseModel(Model):
    """Shared database columns matching the legacy SQLAlchemy base."""

    id = fields.UUIDField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        abstract = True

