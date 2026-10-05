from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.users.users import User


class PasswordResetModel(TortoiseModel):
    __tablename__ = "password_reset_tokens"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="password_reset_tokens",
        source_field="user_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    token = fields.CharField(max_length=64, null=False, unique=True)

    class Meta:
        table = "password_reset_tokens"
