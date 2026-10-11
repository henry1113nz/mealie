from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class RecipeIngredientRefLink(RecipeBase):
    instruction_id: UUID | None
    instruction: fields.ForeignKeyNullableRelation[RecipeInstruction] = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="ingredient_references",
        source_field="instruction_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    reference_id: fields.UUIDField[UUID | None] = UUIDField(null=True, db_index=True)

    class Meta:
        table = "recipe_ingredient_ref_link"


class RecipeInstruction(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="recipe_instructions",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    position: fields.IntField[int | None] = fields.IntField(null=True, db_index=True)
    type: fields.TextField[str | None] = UnboundedCharField(null=True, default="")
    title: fields.TextField[str | None] = UnboundedCharField(null=True)
    text: fields.TextField[str | None] = UnboundedCharField(null=True)
    summary: fields.TextField[str | None] = UnboundedCharField(null=True)
    ingredient_references: fields.ReverseRelation[RecipeIngredientRefLink]
    note_references: fields.ReverseRelation[RecipeNoteRefLink]

    class Meta:
        table = "recipe_instructions"
        ordering = ("position",)


class RecipeNoteRefLink(RecipeBase):
    instruction_id: UUID | None
    instruction: fields.ForeignKeyNullableRelation[RecipeInstruction] = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="note_references",
        source_field="instruction_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    reference_id: fields.UUIDField[UUID | None] = UUIDField(null=True, db_index=True)

    class Meta:
        table = "recipe_note_ref_link"
