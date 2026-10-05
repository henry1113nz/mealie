from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class AIProviderHeaders(TortoiseModel):
    __tablename__ = "ai_provider_headers"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    provider_id: UUID
    provider: fields.ForeignKeyRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="request_headers",
        source_field="provider_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "ai_provider_headers"


class AIProviderParams(TortoiseModel):
    __tablename__ = "ai_provider_params"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    provider_id: UUID
    provider: fields.ForeignKeyRelation[AIProvider] = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="request_params",
        source_field="provider_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "ai_provider_params"


class AIProvider(TortoiseModel):
    __tablename__ = "ai_providers"
    __filterable_fields__ = set()
    __association_proxies__ = {"group_id": ["settings", "group_id"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    settings_id: UUID
    settings: fields.ForeignKeyRelation[AIProviderSettings] = fields.ForeignKeyField(
        "models.AIProviderSettings",
        related_name="providers",
        source_field="settings_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = StringField(null=False, db_index=True)
    base_url = fields.TextField(null=True)
    api_key = fields.TextField(null=False)
    model = fields.TextField(null=False)
    timeout = fields.IntField(null=False, default=300)

    @property
    def group_id(self):
        parent = getattr(self, "settings", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    class Meta:
        table = "ai_providers"
        unique_together = (("name", "settings_id"),)


class AIProviderSettings(TortoiseModel):
    __tablename__ = "ai_provider_settings"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.OneToOneRelation[Group] = fields.OneToOneField(
        "models.Group",
        related_name="ai_provider_settings",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    # Optional selections point back to providers owned by these settings. Scalar
    # UUIDs break the dependency cycle; the repository validates ownership.
    default_provider_id = fields.UUIDField(null=True, db_index=True)
    audio_provider_id = fields.UUIDField(null=True, db_index=True)
    image_provider_id = fields.UUIDField(null=True, db_index=True)

    @property
    def default_provider(self):
        return AIProvider.filter(id=self.default_provider_id, settings_id=self.id).first()

    @property
    def audio_provider(self):
        return AIProvider.filter(id=self.audio_provider_id, settings_id=self.id).first()

    @property
    def image_provider(self):
        return AIProvider.filter(id=self.image_provider_id, settings_id=self.id).first()

    class Meta:
        table = "ai_provider_settings"
        unique_together = (("group_id",),)
