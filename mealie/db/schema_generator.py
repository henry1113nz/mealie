"""DDL shared by Aerich and explicit test schema generation.

SQLite permits forward foreign-key references. PostgreSQL needs the constraints
added after all tables exist, because recipes/users and AI settings/providers
reference each other. Neither backend drops or disables these constraints.
"""

from typing import Any

from tortoise import Model
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.backends.base.schema_generator import BaseSchemaGenerator
from tortoise.backends.base_postgres.schema_generator import BasePostgresSchemaGenerator
from tortoise.backends.sqlite.schema_generator import SqliteSchemaGenerator
from tortoise.fields.relational import ManyToManyFieldInstance

SUBSTITUTION_CHECKS: dict[str, tuple[tuple[str, str], ...]] = {
    "ingredient_foods_substitutions": (
        ("ingredient_foods_substitutions_no_self_substitution", '"food_id" != "substitute_food_id"'),
        ("ingredient_foods_substitutions_food_or_note", '"substitute_food_id" IS NOT NULL OR "note" IS NOT NULL'),
    ),
    "recipes_ingredients_substitutions": (
        ("recipes_ingredients_substitutions_food_or_note", '"substitute_food_id" IS NOT NULL OR "note" IS NOT NULL'),
    ),
}

POSTGRES_TEXT_INDEXES = (
    ("recipes", "name_normalized"),
    ("recipes", "description_normalized"),
    ("recipes_ingredients", "note_normalized"),
    ("recipes_ingredients", "original_text_normalized"),
)


class MealieSchemaGenerator(BaseSchemaGenerator):
    """Preserve constraints and indexes not expressed by Tortoise's model API."""

    _creating_table: str | None = None
    # The existing association tables permit nulls in either join column.
    # Keep this storage contract even though normal relation writes supply both.
    M2M_TABLE_TEMPLATE = BaseSchemaGenerator.M2M_TABLE_TEMPLATE.replace(" NOT NULL", "")

    def __init__(self, client: BaseDBAsyncClient) -> None:
        super().__init__(client)
        self._deferred_foreign_keys: list[str] = []
        self._defer_foreign_keys = False

    def _get_table_sql(self, model: type[Model], safe: bool = True) -> dict[str, Any]:
        self._creating_table = model._meta.db_table
        try:
            return super()._get_table_sql(model, safe)
        finally:
            self._creating_table = None

    def _get_inner_statements(self) -> list[str]:
        checks = SUBSTITUTION_CHECKS.get(self._creating_table or "", ())
        return [*super()._get_inner_statements(), *(f'CONSTRAINT "{name}" CHECK ({sql})' for name, sql in checks)]

    def _get_m2m_tables(self, model: type[Model], db_table: str, safe: bool, models_tables: list[str]) -> list[str]:
        # Join tables are emitted after all ordinary tables, so their foreign
        # keys can remain inline on PostgreSQL too.
        self._creating_table = None
        statements = super()._get_m2m_tables(model, db_table, safe, models_tables)
        for field_name in sorted(model._meta.m2m_fields):
            field = model._meta.fields_map[field_name]
            if not isinstance(field, ManyToManyFieldInstance) or field._generated or field.through in models_tables:
                continue
            for column in (field.backward_key, field.forward_key):
                exists = "IF NOT EXISTS " if safe else ""
                table = self._qualify_table_name(field.through, model._meta.schema)
                statements.append(f'CREATE INDEX {exists}"ix_{field.through}_{column}" ON {table} ("{column}");')
        return statements

    def get_create_schema_sql(self, safe: bool = True) -> str:
        models = self._get_models_to_create()
        self._deferred_foreign_keys = []
        schemas = dict.fromkeys(model._meta.schema for model in models if model._meta.schema)
        statements = [sql for schema in schemas if (sql := self._get_schema_create_sql(schema, safe))]
        self._defer_foreign_keys = True
        try:
            tables = [self._get_table_sql(model, safe) for model in models]
        finally:
            self._defer_foreign_keys = False
        statements.extend(table["table_creation_string"] for table in tables)
        statements.extend(sql for table in tables for sql in table["m2m_tables"])
        statements.extend(self._deferred_foreign_keys)
        if self.DIALECT == "postgres":
            statements.insert(0, "CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            exists = "IF NOT EXISTS " if safe else ""
            for table_name, column in POSTGRES_TEXT_INDEXES:
                statements.append(
                    f'CREATE INDEX {exists}"ix_{table_name}_{column}_gin" '
                    f'ON "{table_name}" USING gin ("{column}" gin_trgm_ops);'
                )
        return "\n".join(statements)


class MealieSqliteSchemaGenerator(MealieSchemaGenerator, SqliteSchemaGenerator):
    pass


class MealiePostgresSchemaGenerator(MealieSchemaGenerator, BasePostgresSchemaGenerator):
    def _create_fk_string(
        self, constraint_name: str, db_column: str, table: str, field: str, on_delete: str, comment: str
    ) -> str:
        if self._creating_table is None or not self._defer_foreign_keys:
            return super()._create_fk_string(constraint_name, db_column, table, field, on_delete, comment)
        self._deferred_foreign_keys.append(
            f'ALTER TABLE "{self._creating_table}" ADD CONSTRAINT "{constraint_name}" '
            f'FOREIGN KEY ("{db_column}") REFERENCES {table} ("{field}") ON DELETE {on_delete};'
        )
        return comment
