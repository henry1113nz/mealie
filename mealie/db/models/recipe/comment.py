from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class RecipeComment(TortoiseModel):
    __tablename__ = "recipe_comments"
    __filterable_fields__ = set()
    __association_proxies__ = {"group_id": ["recipe", "group_id"], "household_id": ["recipe", "household_id"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    text = fields.TextField(null=True)
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="comments",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="comments",
        source_field="user_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    @property
    def group_id(self):
        parent = getattr(self, "recipe", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "recipe", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "recipe_comments"
