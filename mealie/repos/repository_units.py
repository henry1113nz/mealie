from collections.abc import Iterable

from pydantic import UUID4, BaseModel
from tortoise.transactions import in_transaction

from mealie.db.models.household.shopping_list import ShoppingListItem
from mealie.db.models.recipe.ingredient import IngredientUnitModel, RecipeIngredientModel
from mealie.lang.providers import get_locale_context
from mealie.schema.recipe.recipe_ingredient import IngredientUnit, StandardizedUnitType

from .repository_generic import GroupRepositoryGeneric


class RepositoryUnit(GroupRepositoryGeneric[IngredientUnit, IngredientUnitModel]):
    _standardized_unit_map: dict[str, str] | None = None

    @property
    def standardized_unit_map(self) -> dict[str, str]:
        """A map of potential known units to its standardized name in our seed data"""

        if self._standardized_unit_map is None:
            from .seed.seeders import IngredientUnitsSeeder

            ctx = get_locale_context()
            if ctx:
                locale = ctx[1].key
            else:
                locale = None

            self._standardized_unit_map = {}
            locale_file = IngredientUnitsSeeder.get_file(locale=locale)
            for unit_key, unit in IngredientUnitsSeeder.load_file(locale_file).items():
                for prop in ["name", "plural_name", "abbreviation"]:
                    val = unit.get(prop)
                    if val and isinstance(val, str):
                        self._standardized_unit_map[val.strip().lower()] = unit_key

        return self._standardized_unit_map

    async def _get_unit(self, id: UUID4) -> IngredientUnitModel:
        return await self._query_one(id)

    def _add_standardized_unit(self, data: BaseModel | dict) -> dict:
        if not isinstance(data, dict):
            data = data.model_dump()

        # Don't overwrite user data if it exists
        if data.get("standard_quantity") is not None or data.get("standard_unit") is not None:
            return data

        # Compare name attrs to translation files and see if there's a match to a known standard unit
        for prop in ["name", "plural_name", "abbreviation", "plural_abbreviation"]:
            val = data.get(prop)
            if not (val and isinstance(val, str)):
                continue

            standardized_unit_key = self.standardized_unit_map.get(val.strip().lower())
            if not standardized_unit_key:
                continue

            match standardized_unit_key:
                case "teaspoon":
                    data["standard_quantity"] = 1 / 6
                    data["standard_unit"] = StandardizedUnitType.FLUID_OUNCE
                case "tablespoon":
                    data["standard_quantity"] = 1 / 2
                    data["standard_unit"] = StandardizedUnitType.FLUID_OUNCE
                case "cup":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.CUP
                case "fluid-ounce":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.FLUID_OUNCE
                case "pint":
                    data["standard_quantity"] = 2
                    data["standard_unit"] = StandardizedUnitType.CUP
                case "quart":
                    data["standard_quantity"] = 4
                    data["standard_unit"] = StandardizedUnitType.CUP
                case "gallon":
                    data["standard_quantity"] = 16
                    data["standard_unit"] = StandardizedUnitType.CUP
                case "milliliter":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.MILLILITER
                case "liter":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.LITER
                case "pound":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.POUND
                case "ounce":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.OUNCE
                case "gram":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.GRAM
                case "kilogram":
                    data["standard_quantity"] = 1
                    data["standard_unit"] = StandardizedUnitType.KILOGRAM
                case "milligram":
                    data["standard_quantity"] = 1 / 1000
                    data["standard_unit"] = StandardizedUnitType.GRAM
                case _:
                    continue

        return data

    async def create(self, data: BaseModel | dict) -> IngredientUnit:
        data = self._add_standardized_unit(data)
        return await super().create(data)

    async def create_many(self, data: Iterable[BaseModel | dict]) -> list[IngredientUnit]:
        data = [self._add_standardized_unit(i) for i in data]
        return await super().create_many(data)

    async def merge(self, from_unit: UUID4, to_unit: UUID4) -> IngredientUnit | None:
        source = await self._get_unit(from_unit)
        await self._get_unit(to_unit)
        if from_unit == to_unit:
            return await self.get_one(to_unit)
        async with in_transaction(self.session.connection_name) as connection:
            await RecipeIngredientModel.filter(unit_id=from_unit).using_db(connection).update(unit_id=to_unit)
            await ShoppingListItem.filter(unit_id=from_unit).using_db(connection).update(unit_id=to_unit)
            await source.delete(using_db=connection)
        return await self.get_one(to_unit)
