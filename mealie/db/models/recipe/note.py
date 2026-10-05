from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class Note(TortoiseModel):
    __tablename__ = "notes"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.IntField(primary_key=True)
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="notes",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    title = fields.TextField(null=True)
    text = fields.TextField(null=True)
    reference_id = fields.UUIDField(null=True, db_index=True, default=uuid4)

    class Meta:
        table = "notes"
