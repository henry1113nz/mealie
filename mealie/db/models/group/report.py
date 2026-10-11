from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UTCDateTimeField, UUIDField

if TYPE_CHECKING:
    from .group import Group


def report_timestamp() -> datetime:
    return datetime.now(UTC)


class ReportEntryModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    success: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    message: fields.TextField[str | None] = UnboundedCharField(null=True)
    exception: fields.TextField[str | None] = UnboundedCharField(null=True)
    timestamp: fields.DatetimeField[datetime] = UTCDateTimeField(default=report_timestamp)

    report_id: UUID
    report: fields.ForeignKeyRelation[ReportModel] = fields.ForeignKeyField(
        "models.ReportModel", related_name="entries", source_field="report_id", db_index=True, on_delete=fields.RESTRICT
    )

    class Meta:
        table = "report_entries"


class ReportModel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    name = UnboundedCharField()
    status = UnboundedCharField()
    category = UnboundedCharField(db_index=True)
    timestamp: fields.DatetimeField[datetime] = UTCDateTimeField(default=report_timestamp)

    entries: fields.ReverseRelation[ReportEntryModel]
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group", related_name="group_reports", source_field="group_id", db_index=True, on_delete=fields.RESTRICT
    )

    class Meta:
        table = "group_reports"
