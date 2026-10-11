from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from ..recipe.category import Category
    from ..recipe.tag import Tag
    from ..recipe.tool import Tool
    from .household import Household


class CookBook(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    position = fields.IntField(default=1)
    group_id: UUID | None
    group: fields.ForeignKeyNullableRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="cookbooks",
        source_field="group_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    household_id: UUID | None
    household: fields.ForeignKeyNullableRelation[Household] = fields.ForeignKeyField(
        "models.Household",
        related_name="cookbooks",
        source_field="household_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name = UnboundedCharField()
    slug = UnboundedCharField(db_index=True)
    description: fields.TextField[str | None] = UnboundedCharField(null=True, default="")
    public: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    query_filter_string = UnboundedCharField(default="")
    require_all_categories: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)
    require_all_tags: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)
    require_all_tools: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)

    categories: fields.ManyToManyRelation[Category] = fields.ManyToManyField(
        "models.Category",
        related_name="cookbooks",
        through="cookbooks_to_categories",
        backward_key="cookbook_id",
        forward_key="category_id",
        on_delete=fields.RESTRICT,
    )
    tags: fields.ManyToManyRelation[Tag] = fields.ManyToManyField(
        "models.Tag",
        related_name="cookbooks",
        through="cookbooks_to_tags",
        backward_key="cookbook_id",
        forward_key="tag_id",
        on_delete=fields.RESTRICT,
    )
    tools: fields.ManyToManyRelation[Tool] = fields.ManyToManyField(
        "models.Tool",
        related_name="cookbooks",
        through="cookbooks_to_tools",
        backward_key="cookbook_id",
        forward_key="tool_id",
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "cookbooks"
        unique_together = (("slug", "group"),)

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._household_coexistence import delete_cookbook_dependents

        if using_db is not None:
            await delete_cookbook_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_cookbook_dependents(self.id, connection)
                await super().delete(using_db=connection)
