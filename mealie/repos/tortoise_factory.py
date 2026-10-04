"""Async (Tortoise) repositories, added here as each resource is migrated off SQLAlchemy."""

from functools import cached_property

from pydantic import UUID4

from mealie.db.tortoise import models as tm
from mealie.schema.household.group_events import GroupEventNotifierOut
from mealie.schema.household.group_recipe_action import GroupRecipeActionOut
from mealie.schema.labels import MultiPurposeLabelOut
from mealie.schema.reports.reports import ReportOut

from .tortoise_repository import AsyncGroupRepositoryGeneric, AsyncRepositoryGeneric


class AsyncRepositories:
    def __init__(self, *, group_id: UUID4 | None, household_id: UUID4 | None) -> None:
        self.group_id = group_id
        self.household_id = household_id

    @cached_property
    def group_multi_purpose_labels(self) -> AsyncGroupRepositoryGeneric[MultiPurposeLabelOut, tm.MultiPurposeLabel]:
        return AsyncGroupRepositoryGeneric(tm.MultiPurposeLabel, MultiPurposeLabelOut, group_id=self.group_id)

    @cached_property
    def group_reports(self) -> AsyncGroupRepositoryGeneric[ReportOut, tm.ReportModel]:
        return AsyncGroupRepositoryGeneric(tm.ReportModel, ReportOut, group_id=self.group_id)

    @cached_property
    def group_recipe_actions(self) -> AsyncRepositoryGeneric[GroupRecipeActionOut, tm.GroupRecipeAction]:
        return AsyncRepositoryGeneric(
            tm.GroupRecipeAction, GroupRecipeActionOut, group_id=self.group_id, household_id=self.household_id
        )

    @cached_property
    def group_event_notifier(self) -> AsyncRepositoryGeneric[GroupEventNotifierOut, tm.GroupEventNotifierModel]:
        return AsyncRepositoryGeneric(
            tm.GroupEventNotifierModel, GroupEventNotifierOut, group_id=self.group_id, household_id=self.household_id
        )
