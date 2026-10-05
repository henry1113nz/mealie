from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.household.household import Household
    from mealie.db.models.recipe.recipe import RecipeModel


class HouseholdToRecipe(TortoiseModel):
    __tablename__ = "households_to_recipes"
    __filterable_fields__ = set()
    __association_proxies__ = {"group_id": ["household", "group_id"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    household_id: UUID
    household: fields.ForeignKeyRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="households_to_recipes_household",
        source_field="household_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    recipe_id: UUID
    recipe: fields.ForeignKeyRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="households_to_recipes_recipe",
        source_field="recipe_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    last_made = fields.DatetimeField(null=True)

    @property
    def group_id(self):
        parent = getattr(self, "household", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    class Meta:
        table = "households_to_recipes"
        unique_together = (("household_id", "recipe_id"),)
