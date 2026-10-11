import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from tortoise import Model, fields

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UTCDateTimeField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from .password_reset import PasswordResetModel
    from .user_to_recipe import UserToRecipe


class AuthMethod(enum.Enum):
    MEALIE = "Mealie"
    LDAP = "LDAP"
    OIDC = "OIDC"


class AuthMethodField(fields.CharField):
    """Retain the enum names stored by the existing database schema."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(max_length=6, **kwargs)

    def to_python_value(self, value: Any) -> AuthMethod | None:
        if value is None or isinstance(value, AuthMethod):
            return value
        try:
            return AuthMethod[value]
        except KeyError:
            return AuthMethod(value)

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> str | None:
        method = self.to_python_value(value)
        return method.name if method is not None else None


class User(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    full_name: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    username: fields.TextField[str | None] = UnboundedCharField(null=True, unique=True, db_index=True)
    email: fields.TextField[str | None] = UnboundedCharField(null=True, unique=True, db_index=True)
    password: fields.TextField[str | None] = UnboundedCharField(null=True)
    auth_method = AuthMethodField(default=AuthMethod.MEALIE)
    admin: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    advanced: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)

    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group", related_name="users", source_field="group_id", db_index=True, on_delete=fields.RESTRICT
    )
    # Household and Recipe remain legacy models until C5-C6. Their existing
    # database foreign keys continue to enforce these scalar references.
    household_id: fields.UUIDField[UUID | None] = UUIDField(null=True, db_index=True)
    owned_recipes_id: fields.UUIDField[UUID | None] = UUIDField(null=True)

    cache_key: fields.TextField[str | None] = UnboundedCharField(default="1234", null=True)
    external_avatar_hash: fields.TextField[str | None] = UnboundedCharField(null=True)
    login_attemps: fields.IntField[int | None] = fields.IntField(default=0, null=True)
    locked_at: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True)
    tokens_valid_after: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True)

    show_announcements = fields.BooleanField(default=True)
    last_read_announcement: fields.TextField[str | None] = UnboundedCharField(null=True)
    can_manage_household: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    can_manage: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    can_invite: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    can_organize: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)

    tokens: fields.ReverseRelation[LongLiveToken]
    password_reset_tokens: fields.ReverseRelation[PasswordResetModel]
    ratings: fields.ReverseRelation[UserToRecipe]

    class Meta:
        table = "users"

    def update_password(self, password: str) -> None:
        self.password = password
        # JWT issued-at values are whole seconds. Preserve same-second logins.
        self.tokens_valid_after = datetime.now(UTC).replace(microsecond=0)

    def _set_permissions(
        self,
        admin: bool,
        can_manage_household: bool = False,
        can_manage: bool = False,
        can_invite: bool = False,
        can_organize: bool = False,
        **_: Any,
    ) -> None:
        self.admin = admin
        self.can_manage_household = admin or can_manage_household
        self.can_manage = admin or can_manage
        self.can_invite = admin or can_invite
        self.can_organize = admin or can_organize
        if admin:
            self.advanced = True


class LongLiveToken(TortoiseBase):
    name = UnboundedCharField()
    token = UnboundedCharField(db_index=True)
    user_id: UUID | None
    user: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="tokens",
        source_field="user_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "long_live_tokens"
