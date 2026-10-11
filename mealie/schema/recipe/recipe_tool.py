from pydantic import UUID4, ConfigDict, field_validator

from mealie.schema._mealie import MealieModel


class RecipeToolCreate(MealieModel):
    name: str
    households_with_tool: list[str] = []


class RecipeToolSave(RecipeToolCreate):
    group_id: UUID4


class RecipeToolOut(RecipeToolCreate):
    id: UUID4
    group_id: UUID4
    slug: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("households_with_tool", mode="before")
    def convert_households_to_slugs(cls, v):
        if not v:
            return []

        try:
            return [household.slug for household in v]
        except AttributeError:
            return v


class RecipeToolResponse(RecipeToolOut):
    recipes: list[RecipeSummary] = []
    model_config = ConfigDict(from_attributes=True)


from .recipe import RecipeSummary  # noqa: E402

RecipeToolResponse.model_rebuild()
