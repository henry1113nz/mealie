from tortoise.expressions import Q

from mealie.db.models.household.mealplan import GroupMealPlanRules
from mealie.schema.meal_plan.plan_rules import PlanRulesDay, PlanRulesOut, PlanRulesType

from .repository_household_base import AsyncHouseholdRepository


class RepositoryMealPlanRules(AsyncHouseholdRepository[PlanRulesOut, GroupMealPlanRules]):
    async def get_rules(self, day: PlanRulesDay, entry_type: PlanRulesType) -> list[PlanRulesOut]:
        rules = await (await self._query()).filter(
            Q(day=day) | Q(day__isnull=True) | Q(day=PlanRulesDay.unset.value),
            Q(entry_type=entry_type) | Q(entry_type__isnull=True) | Q(entry_type=PlanRulesType.unset.value),
        )
        return [await self._serialize(entry) for entry in rules]
