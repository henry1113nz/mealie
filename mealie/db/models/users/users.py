from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household


class AuthMethod(enum.StrEnum):
    MEALIE = "Mealie"
    LDAP = "LDAP"
    OIDC = "OIDC"


class LongLiveToken(TortoiseModel):
    __tablename__ = "long_live_tokens"
    __filterable_fields__ = set()
    __association_proxies__ = {"group_id": ["user", "group_id"], "household_id": ["user", "household_id"]}

    name = fields.TextField(null=False)
    token = StringField(null=False, db_index=True)
    user_id: UUID | None
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="tokens",
        source_field="user_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    @property
    def group_id(self):
        parent = getattr(self, "user", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "user", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "long_live_tokens"


class User(TortoiseModel):
    __tablename__ = "users"
    __filterable_fields__ = {"id", "full_name", "household_id", "group_id", "username"}
    __association_proxies__ = {}
    model_config = {
        "exclude": {
            "password",
            "admin",
            "can_manage_household",
            "can_manage",
            "can_invite",
            "can_organize",
            "group",
            "household",
        }
    }

    id = fields.UUIDField(primary_key=True, default=uuid4)
    full_name = StringField(null=True, db_index=True)
    username = StringField(null=True, db_index=True, unique=True)
    email = StringField(null=True, db_index=True, unique=True)
    password = fields.TextField(null=True)
    auth_method = fields.CharEnumField(AuthMethod, null=False, default=AuthMethod.MEALIE)
    admin = fields.BooleanField(null=True, default=False)
    advanced = fields.BooleanField(null=True, default=False)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="users",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="users",
        source_field="household_id",
        null=True,
        on_delete=fields.SET_NULL,
        db_index=True,
    )
    cache_key = fields.TextField(null=True, default="1234")
    external_avatar_hash = fields.TextField(null=True, default=None)
    login_attemps = fields.IntField(null=True, default=0)
    locked_at = fields.DatetimeField(null=True, default=None)
    tokens_valid_after = fields.DatetimeField(null=True, default=None)
    show_announcements = fields.BooleanField(null=False, default=True)
    last_read_announcement = fields.TextField(null=True)
    can_manage_household = fields.BooleanField(null=True, default=False)
    can_manage = fields.BooleanField(null=True, default=False)
    can_invite = fields.BooleanField(null=True, default=False)
    can_organize = fields.BooleanField(null=True, default=False)
    owned_recipes_id = fields.UUIDField(null=True)

    @property
    def owned_recipes(self):
        from mealie.db.models.recipe.recipe import RecipeModel

        return RecipeModel.filter(id=self.owned_recipes_id).first()

    @property
    def group_slug(self) -> str:
        return self.group.slug

    @property
    def household_slug(self) -> str | None:
        return self.household.slug if self.household is not None else None

    def update_password(self, password: str) -> None:
        self.password = password
        self.tokens_valid_after = datetime.now(UTC).replace(microsecond=0)

    class Meta:
        table = "users"
