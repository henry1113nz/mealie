from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class RecipeComment(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    text: fields.TextField[str | None] = UnboundedCharField(null=True)
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="comments",
        source_field="recipe_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="comments",
        source_field="user_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "recipe_comments"
