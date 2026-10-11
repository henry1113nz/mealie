from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.cookbook import CookBook
    from mealie.db.models.household.household import Household
    from mealie.db.models.recipe.recipe import RecipeModel


class Tool(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="tools",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str] = UnboundedCharField(db_index=True)
    slug: fields.TextField[str] = UnboundedCharField(db_index=True)
    on_hand: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=False)
    recipes: fields.ManyToManyRelation[RecipeModel]
    households_with_tool: fields.ManyToManyRelation[Household] = fields.ManyToManyField(
        "models.Household",
        related_name="tools_on_hand",
        through="households_to_tools",
        backward_key="tool_id",
        forward_key="household_id",
        on_delete=fields.RESTRICT,
    )

    cookbooks: fields.ManyToManyRelation[CookBook]

    class Meta:
        table = "tools"
        unique_together = (("slug", "group"),)
