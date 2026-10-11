from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UUIDField

if TYPE_CHECKING:
    from ..recipe.recipe import RecipeModel
    from .users import User


class UserToRecipe(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="ratings", source_field="user_id", db_index=True, on_delete=fields.RESTRICT
    )
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="ratings",
        source_field="recipe_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    rating: fields.FloatField[float | None] = fields.FloatField(null=True, db_index=True)
    is_favorite = fields.BooleanField(db_index=True)

    class Meta:
        table = "users_to_recipes"
        unique_together = (("user", "recipe_id"),)
