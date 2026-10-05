from __future__ import annotations

from uuid import uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField


class Group(TortoiseModel):
    __tablename__ = "groups"
    __filterable_fields__ = {"name", "id", "slug"}
    __association_proxies__ = {}
    model_config = {
        "exclude": {
            "households",
            "users",
            "webhooks",
            "recipe_actions",
            "shopping_lists",
            "cookbooks",
            "preferences",
            "ai_provider_settings",
            "invite_tokens",
            "mealplans",
            "data_exports",
        }
    }

    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = StringField(null=False, db_index=True, unique=True)
    slug = StringField(null=True, db_index=True, unique=True)

    class Meta:
        table = "groups"
