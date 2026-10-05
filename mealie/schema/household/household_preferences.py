from pydantic import UUID4, ConfigDict

from mealie.schema._mealie import MealieModel


class UpdateHouseholdPreferences(MealieModel):
    private_household: bool = True
    show_announcements: bool = True

    lock_recipe_edits_from_other_households: bool = True
    first_day_of_week: int = 0

    # Recipe Defaults
    recipe_public: bool = True
    recipe_show_nutrition: bool = False
    recipe_show_assets: bool = False
    recipe_landscape_view: bool = False
    recipe_disable_comments: bool = False


class CreateHouseholdPreferences(UpdateHouseholdPreferences): ...


class SaveHouseholdPreferences(UpdateHouseholdPreferences):
    household_id: UUID4


class ReadHouseholdPreferences(CreateHouseholdPreferences):
    id: UUID4
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def loader_options(cls) -> list[str]:
        return ["household"]
