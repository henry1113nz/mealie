from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from .group import Group


class AIProviderKV(TortoiseBase):
    key_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    value: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        abstract = True


class AIProviderHeaders(AIProviderKV):
    provider_id: UUID
    provider: fields.ForeignKeyRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="request_headers",
        source_field="provider_id",
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "ai_provider_headers"


class AIProviderParams(AIProviderKV):
    provider_id: UUID
    provider: fields.ForeignKeyRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="request_params",
        source_field="provider_id",
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "ai_provider_params"


class AIProvider(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    settings_id: UUID
    settings: fields.ForeignKeyRelation[AIProviderSettings] = fields.ForeignKeyField(
        "models.AIProviderSettings",
        related_name="providers",
        source_field="settings_id",
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    name = UnboundedCharField(db_index=True)
    base_url: fields.TextField[str | None] = UnboundedCharField(null=True)
    api_key = UnboundedCharField()
    model = UnboundedCharField()
    timeout = fields.IntField(default=300)

    request_headers: fields.ReverseRelation[AIProviderHeaders]
    request_params: fields.ReverseRelation[AIProviderParams]

    class Meta:
        table = "ai_providers"
        unique_together = (("name", "settings"),)


class AIProviderSettings(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.OneToOneRelation[Group] = fields.OneToOneField(
        "models.Group",
        related_name="ai_provider_settings",
        source_field="group_id",
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    providers: fields.ReverseRelation[AIProvider]

    # These selections point back into providers, which already depend on these
    # settings. Retain every foreign key; C7 must create this cycle with deferred
    # DDL when replacing the existing Alembic schema bootstrap.
    default_provider_id: UUID | None
    default_provider: fields.ForeignKeyNullableRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name=False,
        source_field="default_provider_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    audio_provider_id: UUID | None
    audio_provider: fields.ForeignKeyNullableRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name=False,
        source_field="audio_provider_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    image_provider_id: UUID | None
    image_provider: fields.ForeignKeyNullableRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name=False,
        source_field="image_provider_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "ai_provider_settings"
