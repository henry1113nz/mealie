from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase

if TYPE_CHECKING:
    from .users import User


class PasswordResetModel(TortoiseBase):
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="password_reset_tokens",
        source_field="user_id",
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    token = fields.CharField(max_length=64, unique=True)

    class Meta:
        table = "password_reset_tokens"
