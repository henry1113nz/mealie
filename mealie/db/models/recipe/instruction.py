from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeIngredientRefLink(TortoiseModel):
    __tablename__ = "recipe_ingredient_ref_link"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    instruction_id: UUID | None
    instruction: fields.ForeignKeyNullableRelation[RecipeInstruction] = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="ingredient_references",
        source_field="instruction_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    reference_id = fields.UUIDField(null=True, db_index=True)

    class Meta:
        table = "recipe_ingredient_ref_link"


class RecipeNoteRefLink(TortoiseModel):
    __tablename__ = "recipe_note_ref_link"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    instruction_id: UUID | None
    instruction: fields.ForeignKeyNullableRelation[RecipeInstruction] = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="note_references",
        source_field="instruction_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    reference_id = fields.UUIDField(null=True, db_index=True)

    class Meta:
        table = "recipe_note_ref_link"


class RecipeInstruction(TortoiseModel):
    __tablename__ = "recipe_instructions"
    __filterable_fields__ = set()
    __association_proxies__ = {}
    model_config = {"exclude": {"id", "ingredient_references", "note_references"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="recipe_instructions",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    position = fields.IntField(null=True, db_index=True)
    type = fields.TextField(null=True, default="")
    title = fields.TextField(null=True)
    text = fields.TextField(null=True)
    summary = fields.TextField(null=True)

    class Meta:
        table = "recipe_instructions"
        ordering = ("position", "id")
