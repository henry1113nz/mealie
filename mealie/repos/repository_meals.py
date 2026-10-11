from datetime import UTC, datetime, tzinfo

from mealie.db.models.household import GroupMealPlan
from mealie.schema.meal_plan.new_meal import ReadPlanEntry

from .repository_household_base import AsyncHouseholdRepository


class RepositoryMeals(AsyncHouseholdRepository[ReadPlanEntry, GroupMealPlan]):
    async def get_today(self, tz: tzinfo = UTC) -> list[ReadPlanEntry]:
        if not self.household_id:
            raise Exception("household_id not set")
        today = datetime.now(tz=tz).date()
        return [await self._serialize(entry) for entry in await (await self._query()).filter(date=today)]

    async def get_meals_by_date_range(self, start_date: datetime, end_date: datetime) -> list[ReadPlanEntry]:
        if not self.household_id:
            raise Exception("household_id not set")
        plans = await (await self._query()).filter(date__gte=start_date.date(), date__lte=end_date.date())
        return [await self._serialize(entry) for entry in plans]
