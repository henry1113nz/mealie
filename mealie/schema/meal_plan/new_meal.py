from datetime import date
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from mealie.schema._mealie import MealieModel
from mealie.schema.recipe.recipe import RecipeSummary
from mealie.schema.response.pagination import PaginationBase


class PlanEntryType(StrEnum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    side = "side"
    snack = "snack"
    drink = "drink"
    dessert = "dessert"


class CreateRandomEntry(MealieModel):
    date: date
    entry_type: PlanEntryType = PlanEntryType.dinner


class CreatePlanEntry(MealieModel):
    date: date
    entry_type: PlanEntryType = PlanEntryType.breakfast
    title: str = ""
    text: str = ""
    recipe_id: Annotated[UUID | None, Field(validate_default=True)] = None

    @field_validator("recipe_id")
    @classmethod
    def id_or_title(cls, value, info: ValidationInfo):
        if bool(value) is False and bool(info.data["title"]) is False:
            raise ValueError(f"`recipe_id={value}` or `title={info.data['title']}` must be provided")

        return value


class UpdatePlanEntry(CreatePlanEntry):
    id: int
    group_id: UUID
    user_id: UUID


class SavePlanEntry(CreatePlanEntry):
    group_id: UUID
    user_id: UUID
    model_config = ConfigDict(from_attributes=True)


class ReadPlanEntry(UpdatePlanEntry):
    household_id: UUID
    recipe: RecipeSummary | None = None
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def loader_options(cls) -> list[str]:
        return ["recipe__recipe_category", "recipe__tags", "recipe__tools", "user"]


class PlanEntryPagination(PaginationBase):
    items: list[ReadPlanEntry]
