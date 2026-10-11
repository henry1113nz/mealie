from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UUIDField

if TYPE_CHECKING:
    from .household import Household


class HouseholdPreferencesModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    household_id: UUID
    household: fields.ForeignKeyRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="preferences",
        source_field="household_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    private_household: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)
    show_announcements = fields.BooleanField(default=True, null=False)
    lock_recipe_edits_from_other_households: fields.BooleanField[bool | None] = fields.BooleanField(
        default=True, null=True
    )
    first_day_of_week: fields.IntField[int | None] = fields.IntField(default=0, null=True)
    recipe_public: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)
    recipe_show_nutrition: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    recipe_show_assets: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    recipe_landscape_view: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    recipe_disable_comments: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    recipe_disable_amount: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)

    class Meta:
        table = "household_preferences"
