"""Stage 4 database invariants for recipe ingredients and aliases.

This migration is applied after the Aerich initial model schema. The Tortoise
models provide alias surrogate keys and pair uniqueness; this migration adds
the substitution checks and PostgreSQL fuzzy-search indexes.
"""

from __future__ import annotations

import re

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = False

_CHECKS = {
    "ingredient_foods_substitutions": (
        (
            "ingredient_foods_substitutions_no_self_substitution",
            "food_id != substitute_food_id",
        ),
        (
            "ingredient_foods_substitutions_food_or_note",
            "substitute_food_id IS NOT NULL OR note IS NOT NULL",
        ),
    ),
    "recipes_ingredients_substitutions": (
        (
            "recipes_ingredients_substitutions_food_or_note",
            "substitute_food_id IS NOT NULL OR note IS NOT NULL",
        ),
    ),
}

_POSTGRES_TRIGRAM_INDEXES = (
    ("ix_recipes_name_normalized_gin", "recipes", "name_normalized"),
    ("ix_recipes_description_normalized_gin", "recipes", "description_normalized"),
    ("ix_recipes_ingredients_note_normalized_gin", "recipes_ingredients", "note_normalized"),
    (
        "ix_recipes_ingredients_original_text_normalized_gin",
        "recipes_ingredients",
        "original_text_normalized",
    ),
    ("ix_ingredient_foods_name_normalized_gin", "ingredient_foods", "name_normalized"),
    ("ix_ingredient_foods_plural_name_normalized_gin", "ingredient_foods", "plural_name_normalized"),
    ("ix_ingredient_units_name_normalized_gin", "ingredient_units", "name_normalized"),
    ("ix_ingredient_units_plural_name_normalized_gin", "ingredient_units", "plural_name_normalized"),
    (
        "ix_ingredient_units_abbreviation_normalized_gin",
        "ingredient_units",
        "abbreviation_normalized",
    ),
    (
        "ix_ingredient_units_plural_abbreviation_normalized_gin",
        "ingredient_units",
        "plural_abbreviation_normalized",
    ),
    ("ix_ingredient_foods_aliases_name_normalized_gin", "ingredient_foods_aliases", "name_normalized"),
    ("ix_ingredient_units_aliases_name_normalized_gin", "ingredient_units_aliases", "name_normalized"),
)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def _sqlite_table_rebuild(db: BaseDBAsyncClient, table: str, checks: tuple[tuple[str, str], ...], *, adding: bool) -> str:
    table_sql_rows = await db.execute_query_dict(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", [table]
    )
    if not table_sql_rows or not table_sql_rows[0]["sql"]:
        raise RuntimeError(f"Expected SQLite table {table!r} was not found")
    create_sql = table_sql_rows[0]["sql"].rstrip().rstrip(";")

    if adding:
        violations = await db.execute_query_dict(
            f"SELECT COUNT(*) AS count FROM {_quote(table)} WHERE "
            + " OR ".join(f"NOT ({expression})" for _, expression in checks)
        )
        if violations[0]["count"]:
            raise RuntimeError(f"Cannot add Stage 4 checks: {table} contains invalid substitution rows")
        for name, expression in checks:
            clause = f", CONSTRAINT {_quote(name)} CHECK ({expression})"
            create_sql = create_sql[: create_sql.rfind(")")] + clause + create_sql[create_sql.rfind(")") :]
    else:
        for name, expression in checks:
            clause = f", CONSTRAINT {_quote(name)} CHECK ({expression})"
            if clause not in create_sql:
                raise RuntimeError(f"Expected Stage 4 SQLite check {name!r} was not found")
            create_sql = create_sql.replace(clause, "", 1)

    index_rows = await db.execute_query_dict(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        [table],
    )
    index_sql = [row["sql"] for row in index_rows]
    columns = await db.execute_query_dict(f"PRAGMA table_info({_quote(table)})")
    column_names = [row["name"] for row in columns]
    temporary_table = f"__stage4_{table}"
    create_sql = re.sub(
        rf"^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?{re.escape(_quote(table))}",
        f"CREATE TABLE {_quote(temporary_table)}",
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if create_sql == table_sql_rows[0]["sql"].rstrip().rstrip(";") and adding:
        raise RuntimeError(f"Unable to prepare SQLite rebuild for {table!r}")
    create_sql += ";"

    quoted_columns = ", ".join(map(_quote, column_names))
    statements = [
        f"DROP TABLE IF EXISTS {_quote(temporary_table)};",
        create_sql,
        f"INSERT INTO {_quote(temporary_table)} ({quoted_columns}) SELECT {quoted_columns} FROM {_quote(table)};",
        f"DROP TABLE {_quote(table)};",
        f"ALTER TABLE {_quote(temporary_table)} RENAME TO {_quote(table)};",
        *[statement.rstrip().rstrip(";") + ";" for statement in index_sql],
    ]
    return "\n".join(statements)


async def upgrade(db: BaseDBAsyncClient) -> str:
    dialect = db.capabilities.dialect
    if dialect == "sqlite":
        rebuilds = [
            await _sqlite_table_rebuild(db, table, checks, adding=True)
            for table, checks in _CHECKS.items()
        ]
        return "\n".join(rebuilds)
    if dialect == "postgres":
        statements = ["CREATE EXTENSION IF NOT EXISTS pg_trgm;"]
        statements.extend(
            f"ALTER TABLE {_quote(table)} ADD CONSTRAINT {_quote(name)} CHECK ({expression});"
            for table, checks in _CHECKS.items()
            for name, expression in checks
        )
        statements.extend(
            f"CREATE INDEX IF NOT EXISTS {_quote(name)} ON {_quote(table)} USING GIN "
            f"({_quote(column)} gin_trgm_ops);"
            for name, table, column in _POSTGRES_TRIGRAM_INDEXES
        )
        return "\n".join(statements)
    raise RuntimeError(f"Stage 4 schema migration does not support dialect {dialect!r}")


async def downgrade(db: BaseDBAsyncClient) -> str:
    dialect = db.capabilities.dialect
    if dialect == "sqlite":
        rebuilds = [
            await _sqlite_table_rebuild(db, table, checks, adding=False)
            for table, checks in _CHECKS.items()
        ]
        return "\n".join(rebuilds)
    if dialect == "postgres":
        statements = [
            f"ALTER TABLE {_quote(table)} DROP CONSTRAINT IF EXISTS {_quote(name)};"
            for table, checks in _CHECKS.items()
            for name, _ in checks
        ]
        statements.extend(f"DROP INDEX IF EXISTS {_quote(name)};" for name, _, _ in _POSTGRES_TRIGRAM_INDEXES)
        # Keep pg_trgm: it may have been installed before this migration or be used elsewhere.
        return "\n".join(statements)
    raise RuntimeError(f"Stage 4 schema migration does not support dialect {dialect!r}")


MODELS_STATE = (
"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"
    "lId2"
)
