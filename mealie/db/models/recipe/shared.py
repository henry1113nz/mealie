from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeShareTokenModel(TortoiseModel):
    __tablename__ = "recipe_share_tokens"
    __filterable_fields__ = {"expires_at", "group_id", "recipe_id"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="recipe_share_tokens_group",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="share_tokens",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    expires_at = fields.DatetimeField(null=False)

    class Meta:
        table = "recipe_share_tokens"
