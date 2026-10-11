from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.recipe.ingredient import IngredientFoodModel


class MultiPurposeLabel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    name: fields.CharField[str] = fields.CharField(max_length=255)
    color: fields.CharField[str] = fields.CharField(max_length=10, default="")
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="labels",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    foods: fields.ReverseRelation[IngredientFoodModel]

    class Meta:
        table = "multi_purpose_labels"
        unique_together = (("name", "group"),)
