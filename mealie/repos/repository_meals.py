from datetime import UTC, datetime

from mealie.db.models.household import GroupMealPlan
from mealie.schema.meal_plan.new_meal import ReadPlanEntry

from .repository_generic import HouseholdRepositoryGeneric


class RepositoryMeals(HouseholdRepositoryGeneric[ReadPlanEntry, GroupMealPlan]):
    async def get_today(self, tz=UTC) -> list[ReadPlanEntry]:
        if not self.household_id:
            raise Exception("household_id not set")
        return await self._to_schemas(
            await self._query().filter(date=datetime.now(tz=tz).date(), **self._filter_builder())
        )

    async def get_meals_by_date_range(self, start_date: datetime, end_date: datetime) -> list[ReadPlanEntry]:
        if not self.household_id:
            raise Exception("household_id not set")
        return await self._to_schemas(
            await self._query().filter(date__gte=start_date.date(), date__lte=end_date.date(), **self._filter_builder())
        )
