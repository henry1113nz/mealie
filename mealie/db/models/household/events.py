from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household


class GroupEventNotifierOptionsModel(TortoiseModel):
    __tablename__ = "group_events_notifier_options"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    event_notifier_id: UUID
    event_notifier: fields.OneToOneRelation[GroupEventNotifierModel] = fields.OneToOneField(
        "models.GroupEventNotifierModel",
        related_name="options",
        source_field="event_notifier_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    recipe_created = fields.BooleanField(null=False, default=False)
    recipe_updated = fields.BooleanField(null=False, default=False)
    recipe_deleted = fields.BooleanField(null=False, default=False)
    user_signup = fields.BooleanField(null=False, default=False)
    data_migrations = fields.BooleanField(null=False, default=False)
    data_export = fields.BooleanField(null=False, default=False)
    data_import = fields.BooleanField(null=False, default=False)
    mealplan_entry_created = fields.BooleanField(null=False, default=False)
    mealplan_entry_updated = fields.BooleanField(null=False, default=False)
    mealplan_entry_deleted = fields.BooleanField(null=False, default=False)
    shopping_list_created = fields.BooleanField(null=False, default=False)
    shopping_list_updated = fields.BooleanField(null=False, default=False)
    shopping_list_deleted = fields.BooleanField(null=False, default=False)
    cookbook_created = fields.BooleanField(null=False, default=False)
    cookbook_updated = fields.BooleanField(null=False, default=False)
    cookbook_deleted = fields.BooleanField(null=False, default=False)
    tag_created = fields.BooleanField(null=False, default=False)
    tag_updated = fields.BooleanField(null=False, default=False)
    tag_deleted = fields.BooleanField(null=False, default=False)
    category_created = fields.BooleanField(null=False, default=False)
    category_updated = fields.BooleanField(null=False, default=False)
    category_deleted = fields.BooleanField(null=False, default=False)
    label_created = fields.BooleanField(null=False, default=False)
    label_updated = fields.BooleanField(null=False, default=False)
    label_deleted = fields.BooleanField(null=False, default=False)

    class Meta:
        table = "group_events_notifier_options"


class GroupEventNotifierModel(TortoiseModel):
    __tablename__ = "group_events_notifiers"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = fields.TextField(null=False)
    enabled = fields.BooleanField(null=False, default=True)
    apprise_url = fields.TextField(null=False)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="group_event_notifiers",
        source_field="group_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="group_event_notifiers",
        source_field="household_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    class Meta:
        table = "group_events_notifiers"
