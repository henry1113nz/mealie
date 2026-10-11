from collections.abc import Callable
from functools import cached_property

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseCrudController
from mealie.routes._base.controller import controller
from mealie.routes._base.mixins import AsyncHttpRepo
from mealie.schema.household.group_shopping_list import (
    ShoppingListAddRecipeParams,
    ShoppingListAddRecipeParamsBulk,
    ShoppingListCreate,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListItemPagination,
    ShoppingListItemsCollectionOut,
    ShoppingListItemUpdate,
    ShoppingListItemUpdateBulk,
    ShoppingListMultiPurposeLabelUpdate,
    ShoppingListOut,
    ShoppingListPagination,
    ShoppingListRemoveRecipeParams,
    ShoppingListSave,
    ShoppingListSummary,
    ShoppingListUpdate,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.responses import SuccessResponse
from mealie.services.event_bus_service.event_types import (
    EventOperation,
    EventShoppingListData,
    EventShoppingListItemBulkData,
    EventTypes,
)
from mealie.services.household_services.shopping_lists import ShoppingListService

item_router = APIRouter(prefix="/households/shopping/items", tags=["Households: Shopping List Items"])


async def publish_list_item_events(publisher: Callable, items_collection: ShoppingListItemsCollectionOut) -> None:
    items_by_list_id: dict[UUID4, list[ShoppingListItemOut]]
    if items_collection.created_items:
        items_by_list_id = {}
        for item in items_collection.created_items:
            items_by_list_id.setdefault(item.shopping_list_id, []).append(item)

        for shopping_list_id, items in items_by_list_id.items():
            await publisher(
                EventTypes.shopping_list_updated,
                document_data=EventShoppingListItemBulkData(
                    operation=EventOperation.create,
                    shopping_list_id=shopping_list_id,
                    shopping_list_item_ids=[item.id for item in items],
                ),
                # since these are all the same shopping list, they share a group_id and household_id
                group_id=items[0].group_id,
                household_id=items[0].household_id,
            )

    if items_collection.updated_items:
        items_by_list_id = {}
        for item in items_collection.updated_items:
            items_by_list_id.setdefault(item.shopping_list_id, []).append(item)

        for shopping_list_id, items in items_by_list_id.items():
            await publisher(
                EventTypes.shopping_list_updated,
                document_data=EventShoppingListItemBulkData(
                    operation=EventOperation.update,
                    shopping_list_id=shopping_list_id,
                    shopping_list_item_ids=[item.id for item in items],
                ),
                # since these are all the same shopping list, they share a group_id and household_id
                group_id=items[0].group_id,
                household_id=items[0].household_id,
            )

    if items_collection.deleted_items:
        items_by_list_id = {}
        for item in items_collection.deleted_items:
            items_by_list_id.setdefault(item.shopping_list_id, []).append(item)

        for shopping_list_id, items in items_by_list_id.items():
            await publisher(
                EventTypes.shopping_list_updated,
                document_data=EventShoppingListItemBulkData(
                    operation=EventOperation.delete,
                    shopping_list_id=shopping_list_id,
                    shopping_list_item_ids=[item.id for item in items],
                ),
                # since these are all the same shopping list, they share a group_id and household_id
                group_id=items[0].group_id,
                household_id=items[0].household_id,
            )


@controller(item_router)
class ShoppingListItemController(BaseCrudController):
    @cached_property
    def service(self):
        return ShoppingListService(self.repos)

    @cached_property
    def repo(self):
        return self.repos.group_shopping_list_item

    @cached_property
    def mixins(self):
        return AsyncHttpRepo[ShoppingListItemCreate, ShoppingListItemOut, ShoppingListItemCreate](
            self.repo,
            self.logger,
        )

    @item_router.get("", response_model=ShoppingListItemPagination)
    async def get_all(self, q: PaginationQuery = Depends()):
        response = await self.repo.page_all(pagination=q, override=ShoppingListItemOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @item_router.post("/create-bulk", response_model=ShoppingListItemsCollectionOut, status_code=201)
    async def create_many(self, data: list[ShoppingListItemCreate]):
        items = await self.service.bulk_create_items(data)
        await publish_list_item_events(self.publish_event, items)
        return items

    @item_router.post("", response_model=ShoppingListItemsCollectionOut, status_code=201)
    async def create_one(self, data: ShoppingListItemCreate):
        return await self.create_many([data])

    @item_router.get("/{item_id}", response_model=ShoppingListItemOut)
    async def get_one(self, item_id: UUID4):
        return await self.mixins.get_one(item_id)

    @item_router.put("", response_model=ShoppingListItemsCollectionOut)
    async def update_many(self, data: list[ShoppingListItemUpdateBulk]):
        items = await self.service.bulk_update_items(data)
        await publish_list_item_events(self.publish_event, items)
        return items

    @item_router.put("/{item_id}", response_model=ShoppingListItemsCollectionOut)
    async def update_one(self, item_id: UUID4, data: ShoppingListItemUpdate):
        return await self.update_many([data.cast(ShoppingListItemUpdateBulk, id=item_id)])

    @item_router.delete("", response_model=SuccessResponse)
    async def delete_many(self, ids: list[UUID4] = Query(None)):
        items = await self.service.bulk_delete_items(ids)
        await publish_list_item_events(self.publish_event, items)
        return SuccessResponse.respond()

    @item_router.delete("/{item_id}", response_model=SuccessResponse)
    async def delete_one(self, item_id: UUID4):
        return await self.delete_many([item_id])


router = APIRouter(prefix="/households/shopping/lists", tags=["Households: Shopping Lists"])


@controller(router)
class ShoppingListController(BaseCrudController):
    @cached_property
    def service(self):
        return ShoppingListService(self.repos)

    @cached_property
    def repo(self):
        return self.repos.group_shopping_lists

    # =======================================================================
    # CRUD Operations

    @cached_property
    def mixins(self) -> AsyncHttpRepo[ShoppingListCreate, ShoppingListOut, ShoppingListSave]:
        return AsyncHttpRepo(self.repo, self.logger, self.registered_exceptions)

    @router.get("", response_model=ShoppingListPagination)
    async def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = await self.repo.page_all(
            pagination=q,
            override=ShoppingListSummary,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.post("", response_model=ShoppingListOut, status_code=201)
    async def create_one(self, data: ShoppingListCreate):
        shopping_list = await self.service.create_one_list(data, self.user.id)
        if shopping_list:
            await self.publish_event(
                event_type=EventTypes.shopping_list_created,
                document_data=EventShoppingListData(operation=EventOperation.create, shopping_list_id=shopping_list.id),
                group_id=shopping_list.group_id,
                household_id=shopping_list.household_id,
                message=self.t("notifications.generic-created", name=shopping_list.name),
            )

        return shopping_list

    @router.get("/{item_id}", response_model=ShoppingListOut)
    async def get_one(self, item_id: UUID4):
        return await self.mixins.get_one(item_id)

    @router.put("/{item_id}", response_model=ShoppingListOut)
    async def update_one(self, item_id: UUID4, data: ShoppingListUpdate):
        shopping_list = await self.mixins.update_one(data, item_id)
        await self.publish_event(
            event_type=EventTypes.shopping_list_updated,
            document_data=EventShoppingListData(operation=EventOperation.update, shopping_list_id=shopping_list.id),
            group_id=shopping_list.group_id,
            household_id=shopping_list.household_id,
            message=self.t("notifications.generic-updated", name=shopping_list.name),
        )

        return shopping_list

    @router.delete("/{item_id}", response_model=ShoppingListOut)
    async def delete_one(self, item_id: UUID4):
        shopping_list = await self.mixins.delete_one(item_id)  # type: ignore
        if shopping_list:
            await self.publish_event(
                event_type=EventTypes.shopping_list_deleted,
                document_data=EventShoppingListData(operation=EventOperation.delete, shopping_list_id=shopping_list.id),
                group_id=shopping_list.group_id,
                household_id=shopping_list.household_id,
                message=self.t("notifications.generic-deleted", name=shopping_list.name),
            )

        return shopping_list

    # =======================================================================
    # Other Operations

    @router.put("/{item_id}/label-settings", response_model=ShoppingListOut)
    async def update_label_settings(self, item_id: UUID4, data: list[ShoppingListMultiPurposeLabelUpdate]):
        for setting in data:
            if setting.shopping_list_id != item_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"object {setting.id} has an invalid shopping list id",
                )

        await self.repos.shopping_list_multi_purpose_labels.update_many(data)
        updated_list = await self.get_one(item_id)

        await self.publish_event(
            event_type=EventTypes.shopping_list_updated,
            document_data=EventShoppingListData(operation=EventOperation.update, shopping_list_id=updated_list.id),
            group_id=updated_list.group_id,
            household_id=updated_list.household_id,
            message=self.t("notifications.generic-updated", name=updated_list.name),
        )

        return updated_list

    @router.post("/{item_id}/recipe", response_model=ShoppingListOut)
    async def add_recipe_ingredients_to_list(self, item_id: UUID4, data: list[ShoppingListAddRecipeParamsBulk]):
        shopping_list, items = await self.service.add_recipe_ingredients_to_list(item_id, data)

        await publish_list_item_events(self.publish_event, items)
        return shopping_list

    @router.post("/{item_id}/recipe/{recipe_id}", response_model=ShoppingListOut, deprecated=True)
    async def add_single_recipe_ingredients_to_list(
        self, item_id: UUID4, recipe_id: UUID4, data: ShoppingListAddRecipeParams | None = None
    ):
        # Compatibility function for old API
        # TODO: remove this function in the future

        data = data or ShoppingListAddRecipeParams(recipe_increment_quantity=1)
        bulk_data = [data.cast(ShoppingListAddRecipeParamsBulk, recipe_id=recipe_id)]
        return await self.add_recipe_ingredients_to_list(item_id, bulk_data)

    @router.post("/{item_id}/recipe/{recipe_id}/delete", response_model=ShoppingListOut)
    async def remove_recipe_ingredients_from_list(
        self, item_id: UUID4, recipe_id: UUID4, data: ShoppingListRemoveRecipeParams | None = None
    ):
        shopping_list, items = await self.service.remove_recipe_ingredients_from_list(
            item_id, recipe_id, data.recipe_decrement_quantity if data else 1
        )

        await publish_list_item_events(self.publish_event, items)
        return shopping_list
