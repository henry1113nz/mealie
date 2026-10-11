from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from .household import Household


class GroupEventNotifierOptionsModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    event_notifier_id: UUID
    event_notifier: fields.ForeignKeyRelation[GroupEventNotifierModel] = fields.ForeignKeyField(
        "models.GroupEventNotifierModel",
        related_name="options",
        source_field="event_notifier_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    recipe_created = fields.BooleanField(default=False, null=False)
    recipe_updated = fields.BooleanField(default=False, null=False)
    recipe_deleted = fields.BooleanField(default=False, null=False)
    user_signup = fields.BooleanField(default=False, null=False)
    data_migrations = fields.BooleanField(default=False, null=False)
    data_export = fields.BooleanField(default=False, null=False)
    data_import = fields.BooleanField(default=False, null=False)
    mealplan_entry_created = fields.BooleanField(default=False, null=False)
    mealplan_entry_updated = fields.BooleanField(default=False, null=False)
    mealplan_entry_deleted = fields.BooleanField(default=False, null=False)
    shopping_list_created = fields.BooleanField(default=False, null=False)
    shopping_list_updated = fields.BooleanField(default=False, null=False)
    shopping_list_deleted = fields.BooleanField(default=False, null=False)
    cookbook_created = fields.BooleanField(default=False, null=False)
    cookbook_updated = fields.BooleanField(default=False, null=False)
    cookbook_deleted = fields.BooleanField(default=False, null=False)
    tag_created = fields.BooleanField(default=False, null=False)
    tag_updated = fields.BooleanField(default=False, null=False)
    tag_deleted = fields.BooleanField(default=False, null=False)
    category_created = fields.BooleanField(default=False, null=False)
    category_updated = fields.BooleanField(default=False, null=False)
    category_deleted = fields.BooleanField(default=False, null=False)
    label_created = fields.BooleanField(default=False, null=False)
    label_updated = fields.BooleanField(default=False, null=False)
    label_deleted = fields.BooleanField(default=False, null=False)

    class Meta:
        table = "group_events_notifier_options"


class GroupEventNotifierModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    name = UnboundedCharField()
    enabled = fields.BooleanField(default=True, null=False)
    apprise_url = UnboundedCharField()
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="group_event_notifiers",
        source_field="group_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="group_event_notifiers",
        source_field="household_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )

    options: fields.ReverseRelation[GroupEventNotifierOptionsModel]

    class Meta:
        table = "group_events_notifiers"

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._household_coexistence import delete_notifier_dependents

        if using_db is not None:
            await delete_notifier_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_notifier_dependents(self.id, connection)
                await super().delete(using_db=connection)
