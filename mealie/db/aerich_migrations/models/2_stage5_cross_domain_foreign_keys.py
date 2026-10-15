"""Add the cyclic Stage 5 cross-domain foreign keys.

The Tortoise relations deliberately use ``db_constraint=False`` so the baseline
can create all referenced tables first. This ordered migration installs the same
constraints in SQLite and PostgreSQL while retaining ORM relation loading.
"""

from __future__ import annotations

import re

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True

_FOREIGN_KEYS = {
    "ai_provider_settings": (
        (
            "fk_ai_provider_settings_default_provider_id_ai_providers",
            "default_provider_id",
            "ai_providers",
        ),
        (
            "fk_ai_provider_settings_audio_provider_id_ai_providers",
            "audio_provider_id",
            "ai_providers",
        ),
        (
            "fk_ai_provider_settings_image_provider_id_ai_providers",
            "image_provider_id",
            "ai_providers",
        ),
    ),
    "users": (("fk_users_owned_recipes_id_recipes", "owned_recipes_id", "recipes"),),
}


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _clause(name: str, column: str, target: str) -> str:
    return (
        f", CONSTRAINT {_quote(name)} FOREIGN KEY ({_quote(column)}) "
        f"REFERENCES {_quote(target)} ({_quote('id')}) ON DELETE NO ACTION"
    )


async def _sqlite_rebuild(db: BaseDBAsyncClient, table: str, *, adding: bool) -> list[str]:
    rows = await db.execute_query_dict(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", [table]
    )
    if not rows or not rows[0]["sql"]:
        raise RuntimeError(f"Expected SQLite table {table!r} was not found")
    original_sql = rows[0]["sql"].rstrip().rstrip(";")
    create_sql = original_sql

    foreign_keys = _FOREIGN_KEYS[table]
    if adding:
        for name, column, target in foreign_keys:
            clause = _clause(name, column, target)
            if clause in create_sql:
                raise RuntimeError(f"Stage 5 foreign key {name!r} already exists")
            insert_at = create_sql.rfind(")")
            if insert_at < 0:
                raise RuntimeError(f"Unable to parse SQLite table DDL for {table!r}")
            create_sql = create_sql[:insert_at] + clause + create_sql[insert_at:]
    else:
        for name, column, target in foreign_keys:
            clause = _clause(name, column, target)
            if clause not in create_sql:
                raise RuntimeError(f"Expected Stage 5 foreign key {name!r} was not found")
            create_sql = create_sql.replace(clause, "", 1)

    index_rows = await db.execute_query_dict(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        [table],
    )
    index_sql = [row["sql"] for row in index_rows]
    columns = await db.execute_query_dict(f"PRAGMA table_info({_quote(table)})")
    column_names = [row["name"] for row in columns]
    if not column_names:
        raise RuntimeError(f"SQLite table {table!r} has no columns")

    temporary_table = f"__stage5_{table}"
    create_sql = re.sub(
        rf"^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?{re.escape(_quote(table))}",
        f"CREATE TABLE {_quote(temporary_table)}",
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if f"CREATE TABLE {_quote(temporary_table)}" not in create_sql:
        raise RuntimeError(f"Unable to prepare SQLite rebuild for {table!r}")

    quoted_columns = ", ".join(_quote(column) for column in column_names)
    statements = [
        f"DROP TABLE IF EXISTS {_quote(temporary_table)}",
        create_sql,
        f"INSERT INTO {_quote(temporary_table)} ({quoted_columns}) "
        f"SELECT {quoted_columns} FROM {_quote(table)}",
        f"DROP TABLE {_quote(table)}",
        f"ALTER TABLE {_quote(temporary_table)} RENAME TO {_quote(table)}",
        *[statement.rstrip().rstrip(";") for statement in index_sql],
    ]
    return statements


async def _sqlite_apply(db: BaseDBAsyncClient, *, adding: bool) -> str:
    # executescript commits any transaction already open on the Aerich connection.
    # Turn FK enforcement off before starting our own atomic table-rebuild transaction.
    await db.execute_script("PRAGMA foreign_keys = OFF;")
    await db.execute_query("BEGIN")
    try:
        for table in _FOREIGN_KEYS:
            for statement in await _sqlite_rebuild(db, table, adding=adding):
                await db.execute_query(statement)
        violations = await db.execute_query_dict("PRAGMA foreign_key_check")
        if violations:
            raise RuntimeError(f"Stage 5 SQLite foreign-key check failed: {violations!r}")
        await db.execute_query("COMMIT")
    except Exception:
        await db.execute_query("ROLLBACK")
        raise
    finally:
        await db.execute_query("PRAGMA foreign_keys = ON")
    # Aerich executes this marker after this function returns. Its executescript
    # commits the transaction opened by Aerich, after the check above succeeds.
    return "-- Stage 5 SQLite table rebuild completed after foreign_key_check."


async def upgrade(db: BaseDBAsyncClient) -> str:
    dialect = db.capabilities.dialect
    if dialect == "sqlite":
        return await _sqlite_apply(db, adding=True)
    if dialect == "postgres":
        return "\n".join(
            f"ALTER TABLE {_quote(table)} ADD CONSTRAINT {_quote(name)} "
            f"FOREIGN KEY ({_quote(column)}) REFERENCES {_quote(target)} ({_quote('id')}) "
            "ON DELETE NO ACTION;"
            for table, foreign_keys in _FOREIGN_KEYS.items()
            for name, column, target in foreign_keys
        )
    raise RuntimeError(f"Stage 5 schema migration does not support dialect {dialect!r}")


async def downgrade(db: BaseDBAsyncClient) -> str:
    dialect = db.capabilities.dialect
    if dialect == "sqlite":
        return await _sqlite_apply(db, adding=False)
    if dialect == "postgres":
        return "\n".join(
            f"ALTER TABLE {_quote(table)} DROP CONSTRAINT IF EXISTS {_quote(name)};"
            for table, foreign_keys in _FOREIGN_KEYS.items()
            for name, _, _ in foreign_keys
        )
    raise RuntimeError(f"Stage 5 schema migration does not support dialect {dialect!r}")
