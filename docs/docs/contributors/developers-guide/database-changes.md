# Development: Database Changes

Database models live under `mealie/db/models/` and use Tortoise ORM. Register new
model modules explicitly in `TORTOISE_MODEL_MODULES` in
`mealie/db/tortoise_config.py`. Both the application and Aerich use this
configuration and the database selected by the normal Mealie settings.

## Generate and apply a migration

Run `task py:migrate -- "add_creation_tag"` to generate an Aerich migration in
`mealie/migrations/models/`. Review the generated SQL and test the migration on
both SQLite and PostgreSQL. Start the backend, or run
`uv run aerich --app models upgrade`, to apply pending migrations.

The initial migration contains separate, checked-in SQL for each supported
backend. Later migrations must also handle both dialects when their DDL differs.
Do not regenerate the initial migration after changing models: generate a new
migration so existing Aerich databases can upgrade.

## Constraints and indexes

`mealie/db/schema_generator.py` preserves details outside Tortoise's model API:
substitution CHECK constraints, single-column indexes on both columns of join
tables, their existing nullable join columns, and PostgreSQL normalized-text GIN
indexes. PostgreSQL creates ordinary
foreign keys after tables so the recipe/user and AI provider/settings cycles
remain enforced; SQLite supports those forward references inline. The initial
PostgreSQL migration also enables `pg_trgm`.

Review changes involving those objects manually, since Aerich's model-state diff
does not describe all of them. Migration scripts must preserve foreign keys;
disabling them is not a solution for cyclic DDL.

This branch starts a new Aerich schema history. Upgrading existing databases
from the previous Alembic history is outside the scope of this rewrite.
