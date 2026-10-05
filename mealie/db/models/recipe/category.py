from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class Category(TortoiseModel):
    __tablename__ = "categories"
    __filterable_fields__ = {"name", "group_id", "id", "slug"}
    __association_proxies__ = {}

    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="categories",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = StringField(null=False, db_index=True)
    slug = StringField(null=False, db_index=True)
    recipe_count: int = 0

    class Meta:
        table = "categories"
        unique_together = (("slug", "group_id"),)
