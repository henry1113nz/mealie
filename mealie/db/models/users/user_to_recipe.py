from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UUIDField

if TYPE_CHECKING:
    from .users import User


class UserToRecipe(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="ratings", source_field="user_id", db_index=True, on_delete=fields.RESTRICT
    )
    # Recipe is converted in C6; the existing database FK remains enforced.
    recipe_id: fields.UUIDField[UUID] = UUIDField(db_index=True)
    rating: fields.FloatField[float | None] = fields.FloatField(null=True, db_index=True)
    is_favorite = fields.BooleanField(db_index=True)

    class Meta:
        table = "users_to_recipes"
        unique_together = (("user", "recipe_id"),)
