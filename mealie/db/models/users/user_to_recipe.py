from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class UserToRecipe(TortoiseModel):
    __tablename__ = "users_to_recipes"
    __filterable_fields__ = set()
    __association_proxies__ = {"group_id": ["recipe", "group_id"], "household_id": ["recipe", "household_id"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="users_to_recipes_user",
        source_field="user_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="users_to_recipes_recipe",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    rating = fields.FloatField(null=True, db_index=True)
    is_favorite = fields.BooleanField(null=False, db_index=True)

    @property
    def group_id(self):
        parent = getattr(self, "recipe", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "recipe", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "users_to_recipes"
        unique_together = (("user_id", "recipe_id"),)
