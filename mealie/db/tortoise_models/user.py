from enum import Enum

from tortoise import fields

from ._base import TortoiseBaseModel


class AuthMethod(str, Enum):
    MEALIE = "Mealie"
    LDAP = "LDAP"
    OIDC = "OIDC"


class User(TortoiseBaseModel):
    full_name = fields.CharField(max_length=255, null=True, db_index=True)
    username = fields.CharField(max_length=255, null=True, unique=True, db_index=True)
    email = fields.CharField(max_length=255, null=True, unique=True, db_index=True)
    password = fields.CharField(max_length=255, null=True)
    auth_method = fields.CharEnumField(AuthMethod, default=AuthMethod.MEALIE)
    admin = fields.BooleanField(default=False, null=True)
    advanced = fields.BooleanField(default=False, null=True)
    group: fields.ForeignKeyRelation["Group"] = fields.ForeignKeyField(
        "models.Group", related_name="users", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    household: fields.ForeignKeyNullableRelation["Household"] = fields.ForeignKeyField(
        "models.Household", related_name="users", null=True, on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    cache_key = fields.CharField(max_length=255, default="1234", null=True)
    external_avatar_hash = fields.CharField(max_length=255, null=True)
    login_attemps = fields.IntField(default=0, null=True)
    locked_at = fields.DatetimeField(null=True)
    tokens_valid_after = fields.DatetimeField(null=True)
    show_announcements = fields.BooleanField(default=True)
    last_read_announcement = fields.CharField(max_length=255, null=True)
    can_manage_household = fields.BooleanField(default=False, null=True)
    can_manage = fields.BooleanField(default=False, null=True)
    can_invite = fields.BooleanField(default=False, null=True)
    can_organize = fields.BooleanField(default=False, null=True)

    class Meta:
        table = "users"

