from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.household.household import Household


class HouseholdPreferencesModel(TortoiseModel):
    __tablename__ = "household_preferences"
    __filterable_fields__ = {
        "recipe_disable_comments",
        "first_day_of_week",
        "recipe_public",
        "id",
        "lock_recipe_edits_from_other_households",
        "recipe_landscape_view",
        "private_household",
        "show_announcements",
        "household_id",
        "recipe_show_assets",
        "recipe_disable_amount",
        "recipe_show_nutrition",
    }
    __association_proxies__ = {"group_id": ["household", "group_id"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    household_id: UUID
    household: fields.OneToOneRelation[Household] = fields.OneToOneField(
        "models.Household",
        related_name="preferences",
        source_field="household_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    private_household = fields.BooleanField(null=True, default=True)
    show_announcements = fields.BooleanField(null=False, default=True)
    lock_recipe_edits_from_other_households = fields.BooleanField(null=True, default=True)
    first_day_of_week = fields.IntField(null=True, default=0)
    recipe_public = fields.BooleanField(null=True, default=True)
    recipe_show_nutrition = fields.BooleanField(null=True, default=False)
    recipe_show_assets = fields.BooleanField(null=True, default=False)
    recipe_landscape_view = fields.BooleanField(null=True, default=False)
    recipe_disable_comments = fields.BooleanField(null=True, default=False)
    recipe_disable_amount = fields.BooleanField(null=True, default=True)

    @property
    def group_id(self):
        parent = getattr(self, "household", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    class Meta:
        table = "household_preferences"
