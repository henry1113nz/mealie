from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel


class Note(RecipeBase):
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="notes",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    title: fields.TextField[str | None] = UnboundedCharField(null=True)
    text: fields.TextField[str | None] = UnboundedCharField(null=True)
    reference_id: fields.UUIDField[UUID | None] = UUIDField(null=True, db_index=True, default=uuid4)

    class Meta:
        table = "notes"
