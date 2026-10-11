"""Common native repository constructors retained for extension consumers."""

from uuid import UUID

from tortoise import Model
from tortoise.backends.base.client import BaseDBAsyncClient

from mealie.schema._mealie import MealieModel

from ._utils import NOT_SET, NotSet
from .repository_users import AsyncUserRepository


class RepositoryGeneric[Schema: MealieModel, DBModel: Model](AsyncUserRepository[Schema, DBModel]):
    def __init__(
        self, session: BaseDBAsyncClient, primary_key: str, sql_model: type[DBModel], schema: type[Schema]
    ) -> None:
        super().__init__(session, primary_key, sql_model, schema, group_id=None)


class GroupRepositoryGeneric[Schema: MealieModel, DBModel: Model](AsyncUserRepository[Schema, DBModel]):
    pass


class HouseholdRepositoryGeneric[Schema: MealieModel, DBModel: Model](AsyncUserRepository[Schema, DBModel]):
    def __init__(
        self,
        session: BaseDBAsyncClient,
        primary_key: str,
        sql_model: type[DBModel],
        schema: type[Schema],
        *,
        group_id: UUID | None | NotSet,
        household_id: UUID | None | NotSet,
    ) -> None:
        super().__init__(session, primary_key, sql_model, schema, group_id=group_id)
        if household_id is NOT_SET:
            raise ValueError("household_id must be set")
        self.household_id = UUID(str(household_id)) if household_id else None
