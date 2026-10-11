from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UTCDateTimeField, UUIDField

if TYPE_CHECKING:
    from .household import Household


class HouseholdToRecipe(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    household_id: UUID
    household: fields.ForeignKeyRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="made_recipe_links",
        source_field="household_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    # The recipe domain remains on the existing schema until C6.
    recipe_id: fields.UUIDField[UUID] = UUIDField(db_index=True)
    last_made: fields.DatetimeField[datetime | None] = UTCDateTimeField(null=True)

    class Meta:
        table = "households_to_recipes"
        unique_together = (("household", "recipe_id"),)
