"""PostgreSQL backend with cycle-aware ordering for migration-only foreign keys."""

from typing import Any

from tortoise.backends.asyncpg.client import AsyncpgDBClient
from tortoise.backends.asyncpg.schema_generator import AsyncpgSchemaGenerator


class MealieAsyncpgSchemaGenerator(AsyncpgSchemaGenerator):
    def _get_field_sql_and_related_table(
        self, field_object: Any, table_name: str, column_name: str, default: str, comment: str
    ) -> tuple[str, str]:
        sql, related_table = super()._get_field_sql_and_related_table(
            field_object, table_name, column_name, default, comment
        )
        reference = getattr(field_object, "reference", None)
        if reference is not None and not reference.db_constraint:
            return sql, ""
        return sql, related_table


class MealieAsyncpgClient(AsyncpgDBClient):
    schema_generator = MealieAsyncpgSchemaGenerator


client_class = MealieAsyncpgClient
