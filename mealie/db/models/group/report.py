from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models._model_utils.datetime import get_utc_now
from mealie.db.models._model_utils.string import StringField

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group


class ReportEntryModel(TortoiseModel):
    __tablename__ = "report_entries"
    __filterable_fields__ = set()
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    success = fields.BooleanField(null=True, default=False)
    message = fields.TextField(null=True)
    exception = fields.TextField(null=True)
    timestamp = fields.DatetimeField(null=False, default=get_utc_now)
    report_id: UUID
    report: fields.ForeignKeyRelation[ReportModel] = fields.ForeignKeyField(
        "models.ReportModel",
        related_name="entries",
        source_field="report_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    class Meta:
        table = "report_entries"


class ReportModel(TortoiseModel):
    __tablename__ = "group_reports"
    __filterable_fields__ = set()
    __association_proxies__ = {}
    model_config = {"exclude": ["entries"]}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    name = fields.TextField(null=False)
    status = fields.TextField(null=False)
    category = StringField(null=False, db_index=True)
    timestamp = fields.DatetimeField(null=False, default=get_utc_now)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="group_reports",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )

    class Meta:
        table = "group_reports"
