from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.ingredient import IngredientFoodModel
    from mealie.db.models.recipe.recipe import RecipeModel


class ApiExtras(RecipeBase):
    recipee_id: UUID | None
    recipee: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="extras",
        source_field="recipee_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    key_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    value: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "api_extras"


class IngredientFoodExtras(RecipeBase):
    ingredient_food_id: UUID | None
    ingredient_food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="extras",
        source_field="ingredient_food_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    key_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    value: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "ingredient_food_extras"
