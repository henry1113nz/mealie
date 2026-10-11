from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from tortoise import Model
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.db.models import _legacy_household
from mealie.db.models.group import Group
from mealie.db.models.household import (
    CookBook,
    GroupEventNotifierModel,
    GroupEventNotifierOptionsModel,
    GroupMealPlan,
    Household,
    HouseholdPreferencesModel,
    HouseholdToRecipe,
    ShoppingList,
    ShoppingListItem,
    ShoppingListItemRecipeReference,
    ShoppingListMultiPurposeLabel,
    ShoppingListRecipeReference,
)
from mealie.db.models.household.shopping_list import ShoppingListExtras, ShoppingListItemExtras
from mealie.db.models.users import User
from mealie.schema._mealie import MealieModel
from mealie.schema.household.group_events import GroupEventNotifierOptionsOut
from mealie.schema.household.group_shopping_list import (
    ShoppingListItemOut,
    ShoppingListItemRecipeRefOut,
    ShoppingListMultiPurposeLabelOut,
    ShoppingListRecipeRefOut,
)
from mealie.schema.household.household_preferences import ReadHouseholdPreferences
from mealie.schema.response.pagination import PaginationQuery

from . import _households_coexistence as recipe_bridge
from . import _users_coexistence as bridge
from ._utils import NOT_SET, NotSet
from .repository_users import AsyncUserRepository, LegacySession


class AsyncHouseholdRepository[Schema: MealieModel, DBModel: Model](AsyncUserRepository[Schema, DBModel]):
    """Async persistence and schema hydration for household-owned data.

    Household ownership of meal plans and shopping lists follows their user,
    while nested shopping rows follow the owning list. Keep those paths explicit
    instead of introducing household columns that are absent from the schema.
    """

    household_id: UUID | None

    def __init__(
        self,
        session: LegacySession,
        primary_key: str,
        sql_model: type[DBModel],
        schema: type[Schema],
        *,
        group_id: UUID | None | NotSet,
        household_id: UUID | None | NotSet = NOT_SET,
    ) -> None:
        super().__init__(session, primary_key, sql_model, schema, group_id=group_id)
        if household_id is NOT_SET and sql_model is not Household:
            raise ValueError("household_id must be set")
        self.household_id = UUID(str(household_id)) if household_id and household_id is not NOT_SET else None

    def _scope_key(self, key: str) -> str:
        root, *suffix = key.split("__", 1)
        if root not in ("group_id", "household_id"):
            return key
        if self.model in (HouseholdPreferencesModel, HouseholdToRecipe):
            result = "household__group_id" if root == "group_id" else root
        elif self.model in (ShoppingList, GroupMealPlan):
            result = root if root == "group_id" else "user__household_id"
        elif self.model in (ShoppingListItem, ShoppingListRecipeReference, ShoppingListMultiPurposeLabel):
            result = "shopping_list__" + (root if root == "group_id" else "user__household_id")
        elif self.model is ShoppingListItemRecipeReference:
            result = "shopping_list_item__shopping_list__" + (root if root == "group_id" else "user__household_id")
        else:
            result = root
        return result + ("__" + suffix[0] if suffix else "")

    def _random_seed(self) -> str:
        return str(datetime.now(UTC))

    async def _query(self) -> QuerySet[DBModel]:
        query = self.model.all()
        if self.group_id:
            query = query.filter(**{self._scope_key("group_id"): self.group_id})
        if self.household_id:
            query = query.filter(**{self._scope_key("household_id"): self.household_id})
        return query

    async def _query_identifiers(self, pagination: PaginationQuery) -> list[Any]:
        model = getattr(_legacy_household, self.model.__name__)
        return await bridge.query_model_ids(model, self.group_id, pagination, household_id=self.household_id)

    async def _query_one(self, match_value: Any, match_key: str | None = None) -> DBModel:
        return await super()._query_one(match_value, self._scope_key(match_key or self.primary_key))

    async def get_one(
        self,
        value: Any,
        key: str | None = None,
        any_case: bool = False,
        override_schema: type[MealieModel] | None = None,
    ) -> Any:
        return await super().get_one(value, self._scope_key(key or self.primary_key), any_case, override_schema)

    async def multi_query(
        self,
        query_by: dict[str, Any],
        start: int = 0,
        limit: int | None = None,
        override_schema: type[MealieModel] | None = None,
        order_by: str | None = None,
    ) -> list[Schema]:
        return await super().multi_query(
            {self._scope_key(key): value for key, value in query_by.items()},
            start,
            limit,
            override_schema,
            self._scope_key(order_by) if order_by else None,
        )

    async def count_all(self, match_key: str | None = None, match_value: Any = None) -> int:
        return await super().count_all(self._scope_key(match_key) if match_key else None, match_value)

    @staticmethod
    def _data(entry: Model) -> dict[str, Any]:
        return {key: getattr(entry, key) for key in entry._meta.db_fields}

    async def _serialize(self, entry: Model, schema: type[MealieModel] | None = None) -> Any:
        target = schema or self.schema
        data = self._data(entry)
        if isinstance(entry, Household):
            group = await Group.get(id=entry.group_id)
            preferences = await HouseholdPreferencesModel.filter(household_id=entry.id).first()
            data.update(
                group=group.name,
                users=await User.filter(household_id=entry.id).values("id", "full_name"),
                preferences=await self._serialize(preferences, ReadHouseholdPreferences) if preferences else None,
            )
            if "webhooks" in target.model_fields:
                from mealie.db.models.household.webhooks import GroupWebhooksModel

                data["webhooks"] = [self._data(row) for row in await GroupWebhooksModel.filter(household_id=entry.id)]
        elif isinstance(entry, CookBook):
            household = await Household.get_or_none(id=entry.household_id)
            data["household"] = {"id": household.id, "name": household.name} if household else None
        elif isinstance(entry, GroupEventNotifierModel):
            options = await GroupEventNotifierOptionsModel.filter(event_notifier_id=entry.id).first()
            data["options"] = await self._serialize(options, GroupEventNotifierOptionsOut) if options else None
        elif isinstance(entry, GroupMealPlan):
            data["household_id"] = await User.filter(id=entry.user_id).first().values_list("household_id", flat=True)
            data["recipe"] = await recipe_bridge.recipe_summary(entry.recipe_id)
        elif isinstance(entry, ShoppingList):
            data["household_id"] = await User.filter(id=entry.user_id).first().values_list("household_id", flat=True)
            data["extras"] = {
                row.key_name: row.value for row in await ShoppingListExtras.filter(shopping_list_id=entry.id)
            }
            for field, model, child_schema, ordering in (
                ("list_items", ShoppingListItem, ShoppingListItemOut, "position"),
                ("recipe_references", ShoppingListRecipeReference, ShoppingListRecipeRefOut, "created_at"),
                ("label_settings", ShoppingListMultiPurposeLabel, ShoppingListMultiPurposeLabelOut, "position"),
            ):
                if field in target.model_fields:
                    data[field] = [
                        await self._serialize(row, child_schema)
                        for row in await model.filter(shopping_list_id=entry.id).order_by(ordering)
                    ]
        elif isinstance(entry, ShoppingListItem):
            shopping_list = await ShoppingList.get(id=entry.shopping_list_id)
            data["group_id"] = shopping_list.group_id
            data["household_id"] = (
                await User.filter(id=shopping_list.user_id).first().values_list("household_id", flat=True)
            )
            data["extras"] = {
                row.key_name: row.value for row in await ShoppingListItemExtras.filter(shopping_list_item_id=entry.id)
            }
            data["recipe_references"] = [
                await self._serialize(row, ShoppingListItemRecipeRefOut)
                for row in await ShoppingListItemRecipeReference.filter(shopping_list_item_id=entry.id)
            ]
            data["food"] = await recipe_bridge.ingredient_food(entry.food_id)
            data["unit"] = await recipe_bridge.ingredient_unit(entry.unit_id)
            data["label"] = await recipe_bridge.label(entry.label_id)
        elif isinstance(entry, ShoppingListRecipeReference):
            data["recipe"] = await recipe_bridge.recipe_summary(entry.recipe_id)
        elif isinstance(entry, ShoppingListMultiPurposeLabel):
            data["label"] = await recipe_bridge.label(entry.label_id)
        return target.model_validate(data)

    async def _prepare(self, data: dict[str, Any], *, creating: bool, entry: DBModel | None = None) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in self.model._meta.db_fields}
        if not creating or values.get("id") is None:
            values.pop("id", None)
        for key in ("created_at", "update_at"):
            if values.get(key) is None:
                values.pop(key, None)
        return values

    async def create(self, data: Schema | BaseModel | dict[str, Any]) -> Schema:
        values = data.copy() if isinstance(data, dict) else data.model_dump()
        async with in_transaction("default"):
            entry = await self.model.create(**await self._prepare(values, creating=True))
            await self._save_nested(entry, values)
            await self._after_write(entry)
            return await self._serialize(entry)

    async def update(self, match_value: Any, new_data: dict[str, Any] | BaseModel) -> Schema:
        values = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        async with in_transaction("default"):
            entry = await self._query_one(match_value)
            entry.update_from_dict(await self._prepare(values, creating=False, entry=entry))
            await entry.save()
            await self._save_nested(entry, values)
            await self._after_write(entry)
            return await self._serialize(entry)

    async def _save_nested(self, entry: Model, data: dict[str, Any]) -> None:
        if isinstance(entry, GroupEventNotifierModel) and "options" in data:
            options_data = data["options"] or {}
            options = await GroupEventNotifierOptionsModel.filter(event_notifier_id=entry.id).first()
            values = {
                key: value
                for key, value in options_data.items()
                if key in GroupEventNotifierOptionsModel._meta.db_fields and key not in ("id", "event_notifier_id")
            }
            if options:
                options.update_from_dict(values)
                await options.save()
            else:
                await GroupEventNotifierOptionsModel.create(event_notifier_id=entry.id, **values)
        elif isinstance(entry, ShoppingList):
            # list_items was excluded by the legacy ShoppingList update config;
            # list item mutations are intentionally handled by their own repo.
            if "extras" in data:
                await self._replace_extras(ShoppingListExtras, "shopping_list_id", entry.id, data["extras"])
            for key, model in (
                ("recipe_references", ShoppingListRecipeReference),
                ("label_settings", ShoppingListMultiPurposeLabel),
            ):
                if key in data:
                    await self._replace_children(model, "shopping_list_id", entry.id, data[key] or [])
        elif isinstance(entry, ShoppingListItem):
            # Missing extras used to clear the collection through @api_extras.
            await self._replace_extras(ShoppingListItemExtras, "shopping_list_item_id", entry.id, data.get("extras"))
            if "recipe_references" in data:
                await self._replace_children(
                    ShoppingListItemRecipeReference, "shopping_list_item_id", entry.id, data["recipe_references"] or []
                )

    async def _replace_extras(self, model: type[Model], parent_key: str, parent_id: UUID, extras: Any) -> None:
        await model.filter(**{parent_key: parent_id}).delete()
        for key, value in (extras or {}).items():
            await model.create(**{parent_key: parent_id, "key_name": key, "value": value})

    async def _replace_children(
        self, model: type[Model], parent_key: str, parent_id: UUID, children: list[dict[str, Any]]
    ) -> None:
        current = {str(row.pk): row for row in await model.filter(**{parent_key: parent_id})}
        retained = set()
        for data in children:
            child_id = str(data["id"]) if data.get("id") else None
            child = current.get(child_id) if child_id else None
            if child_id and child is None and await model.filter(id=child_id).exists():
                raise ValueError("Child does not belong to this parent")
            values = {
                key: value
                for key, value in data.items()
                if key in model._meta.db_fields and key not in ("id", parent_key)
            }
            values[parent_key] = parent_id
            if child:
                child.update_from_dict(values)
                await child.save()
            else:
                child = await model.create(**values)
            retained.add(str(child.pk))
        for child_id, child in current.items():
            if child_id not in retained:
                await child.delete()

    async def _after_write(self, entry: DBModel) -> None:
        if isinstance(entry, ShoppingListItem) and entry.shopping_list_id:
            await ShoppingList.filter(id=entry.shopping_list_id).update(update_at=datetime.now(UTC))
        elif isinstance(entry, HouseholdToRecipe) and entry.last_made:
            # Preserve the historical monotonic value, including on deletion.
            from tortoise.expressions import Q

            from mealie.db.models.recipe.recipe import RecipeModel

            await RecipeModel.filter(
                Q(last_made__isnull=True) | Q(last_made__lt=entry.last_made), id=entry.recipe_id
            ).update(last_made=entry.last_made, update_at=datetime.now(UTC))
        await super()._after_write(entry)
