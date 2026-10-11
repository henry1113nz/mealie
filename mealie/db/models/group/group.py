from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..server.task import ServerTaskModel
    from ..users.users import User
    from .ai_providers import AIProviderSettings
    from .exports import GroupDataExportsModel
    from .preferences import GroupPreferencesModel
    from .report import ReportModel


class Group(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    name = UnboundedCharField(unique=True, db_index=True)
    slug: fields.TextField[str | None] = UnboundedCharField(null=True, unique=True, db_index=True)

    users: fields.ReverseRelation[User]
    server_tasks: fields.ReverseRelation[ServerTaskModel]
    preferences: fields.ReverseRelation[GroupPreferencesModel]
    ai_provider_settings: fields.BackwardOneToOneRelation[AIProviderSettings]
    data_exports: fields.ReverseRelation[GroupDataExportsModel]
    group_reports: fields.ReverseRelation[ReportModel]

    class Meta:
        table = "groups"

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        # Existing tables lack database cascades. Keep every dependent deletion
        # on the same async transaction until the remaining domains migrate.
        from mealie.repos._groups_coexistence import delete_group_dependents

        if using_db is not None:
            await delete_group_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_group_dependents(self.id, connection)
                await super().delete(using_db=connection)
