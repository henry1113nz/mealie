from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household


class CookBook(TortoiseModel):
    __tablename__ = "cookbooks"
    __filterable_fields__ = {
        "require_all_tags",
        "position",
        "name",
        "public",
        "require_all_categories",
        "id",
        "require_all_tools",
        "household_id",
        "group_id",
        "description",
        "slug",
    }
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    position = fields.IntField(null=False, default=1)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="cookbooks",
        source_field="group_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="cookbooks",
        source_field="household_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = fields.TextField(null=False)
    slug = StringField(null=False, db_index=True)
    description = fields.TextField(null=True, default="")
    public = fields.BooleanField(null=True, default=False)
    query_filter_string = fields.TextField(null=False, default="")
    require_all_categories = fields.BooleanField(null=True, default=True)
    require_all_tags = fields.BooleanField(null=True, default=True)
    require_all_tools = fields.BooleanField(null=True, default=True)
    categories = fields.ManyToManyField(
        "models.Category",
        related_name="cookbooks_categories",
        through="cookbooks_to_categories",
        backward_key="cookbook_id",
        forward_key="category_id",
    )
    tags = fields.ManyToManyField(
        "models.Tag",
        related_name="cookbooks_tags",
        through="cookbooks_to_tags",
        backward_key="cookbook_id",
        forward_key="tag_id",
    )
    tools = fields.ManyToManyField(
        "models.Tool",
        related_name="cookbooks_tools",
        through="cookbooks_to_tools",
        backward_key="cookbook_id",
        forward_key="tool_id",
    )

    class Meta:
        table = "cookbooks"
        unique_together = (("slug", "group_id"),)
        ordering = ("position", "id")
