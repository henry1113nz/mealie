"""Regenerate or verify the frozen initial migration with the installed ORM.

Run only while developing the initial Tortoise migration, before releasing it:
    uv run python dev/scripts/generate_tortoise_baseline.py
    uv run python dev/scripts/generate_tortoise_baseline.py --check

Both dialects use Tortoise's schema generators without opening a PostgreSQL
connection. Application startup always executes the checked-in SQL files.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "mealie/db/migrations/models"
MIGRATION = MIGRATIONS / "0_20261005000000_init.py"
sys.path.insert(0, str(ROOT))


def add_constraints(sql: str) -> str:
    constraints = {
        "users": [
            "CONSTRAINT \"users_auth_method_valid\" CHECK (\"auth_method\" IN ('Mealie', 'LDAP', 'OIDC'))",
        ],
        "ingredient_foods_substitutions": [
            'CONSTRAINT "ingredient_foods_substitutions_no_self_substitution" '
            'CHECK ("food_id" <> "substitute_food_id")',
            'CONSTRAINT "ingredient_foods_substitutions_food_or_note" '
            'CHECK ("substitute_food_id" IS NOT NULL OR "note" IS NOT NULL)',
        ],
        "recipes_ingredients_substitutions": [
            'CONSTRAINT "recipes_ingredients_substitutions_food_or_note" '
            'CHECK ("substitute_food_id" IS NOT NULL OR "note" IS NOT NULL)',
        ],
    }
    for table, checks in constraints.items():
        pattern = rf'(CREATE TABLE(?: IF NOT EXISTS)? "{table}" \([\s\S]*?)(\n\);)'
        sql, count = re.subn(
            pattern, lambda match, checks=checks: match[1] + ",\n    " + ",\n    ".join(checks) + match[2], sql
        )
        if count != 1:
            raise ValueError(f"Expected one CREATE TABLE for {table}; found {count}")
    return sql


def canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, list | tuple):
        result = [canonical(item) for item in value]
        if result and all(isinstance(item, dict) and "name" in item for item in result):
            result.sort(key=lambda item: item["name"])
        return result
    return value


async def generate(check: bool) -> None:
    from aerich.utils import decompress_dict, get_formatted_compressed_data, get_models_describe
    from tortoise import Tortoise, connections

    state: dict[str, Any] = {}
    generated: dict[Path, str] = {}
    for dialect, url in (
        ("sqlite", "sqlite://:memory:"),
        ("postgres", "postgres://mealie:mealie@localhost:5432/mealie"),
    ):
        try:
            await Tortoise.init(
                db_url=url,
                modules={"models": ["mealie.db.models._all_models", "aerich.models"]},
                use_tz=False,
                timezone="UTC",
            )
            connection = connections.get("default")
            generator = connection.schema_generator(connection)
            sql = add_constraints(generator.get_create_schema_sql(safe=True))
            if dialect == "postgres":
                sql += "\nCREATE EXTENSION IF NOT EXISTS pg_trgm;\n"
                for model in Tortoise.apps["models"].values():
                    for field in sorted(model._meta.db_fields):
                        if field.endswith("_normalized"):
                            index = generator._get_index_name("gin", model, [field])
                            sql += (
                                f'CREATE INDEX IF NOT EXISTS "{index}" ON "{model._meta.db_table}" '
                                f'USING gin ("{field}" gin_trgm_ops);\n'
                            )
            generated[MIGRATIONS / f"0_initial_{dialect}.sql"] = sql.rstrip() + "\n"
            tables = re.findall(r'CREATE TABLE(?: IF NOT EXISTS)? "([^"]+)"', sql)
            generated[MIGRATIONS / f"0_downgrade_{dialect}.sql"] = "".join(
                f'DROP TABLE IF EXISTS "{table}";\n' for table in reversed(tables) if table != "aerich"
            )
            state = get_models_describe("models")
        finally:
            await Tortoise.close_connections()
    if check:
        tree = ast.parse(MIGRATION.read_text())
        state_node = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MODELS_STATE" for target in node.targets)
        )
        frozen = decompress_dict(ast.literal_eval(state_node))
        if canonical(frozen) != canonical(json.loads(json.dumps(state, default=str))):
            raise SystemExit("Frozen model metadata differs from the native ORM description; regenerate the baseline")
        # DDL formatting is not significant; compare statements independent of order.
        for path, sql in generated.items():

            def normalize(text: str) -> list[str]:
                return sorted(" ".join(part.split()) for part in text.split(";") if part.strip())

            if normalize(path.read_text()) != normalize(sql):
                raise SystemExit(f"Frozen SQL differs from the native schema generator: {path.name}")
        sys.stdout.write("Frozen SQL and model metadata match Tortoise for SQLite and PostgreSQL\n")
        return
    for path, sql in generated.items():
        path.write_text(sql, encoding="utf-8")
    source = MIGRATION.read_text().split("MODELS_STATE = (", 1)[0]
    MIGRATION.write_text(source + "MODELS_STATE = (\n    " + get_formatted_compressed_data(state) + "\n)\n")
    sys.stdout.write("Regenerated frozen SQL and model metadata for SQLite and PostgreSQL\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in artifacts without changing them")
    asyncio.run(generate(parser.parse_args().check))
