"""Async (Tortoise) repositories, added here as each resource is migrated off SQLAlchemy."""

from functools import cached_property

from pydantic import UUID4
from tortoise.transactions import in_transaction

from mealie.db.tortoise import models as tm
from mealie.schema.labels import MultiPurposeLabelOut

from .tortoise_repository import AsyncGroupRepositoryGeneric


class AsyncLabelRepository(AsyncGroupRepositoryGeneric[MultiPurposeLabelOut, tm.MultiPurposeLabel]):
    async def delete(self, value, match_key=None) -> MultiPurposeLabelOut:
        # SQLAlchemy did this through relationship settings on the model: the label's shopping
        # list settings were deleted (delete-orphan) and foods / list items lost the label
        # (default nulling of the foreign key). Tortoise does neither, so it is done here.
        async with in_transaction():
            label = await self._query_one(value, match_key)
            await tm.ShoppingListMultiPurposeLabel.filter(label_id=label.id).delete()
            await tm.ShoppingListItem.filter(label_id=label.id).update(label_id=None)
            await tm.IngredientFoodModel.filter(label_id=label.id).update(label_id=None)
            result = self._to_schema(label)
            await label.delete()
        return result


class AsyncRepositories:
    def __init__(self, *, group_id: UUID4 | None, household_id: UUID4 | None) -> None:
        self.group_id = group_id
        self.household_id = household_id

    @cached_property
    def group_multi_purpose_labels(self) -> AsyncLabelRepository:
        return AsyncLabelRepository(tm.MultiPurposeLabel, MultiPurposeLabelOut, group_id=self.group_id)
