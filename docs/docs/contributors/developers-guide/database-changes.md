# Development: Database Changes

Mealie uses Tortoise ORM with SQLite and PostgreSQL. Models live in
`mealie/db/models/`, and Aerich migrations live in `mealie/db/migrations/models/`.
Database operations in repositories, services, routes, and scheduled tasks are
asynchronous. Await database calls and use `async with session_context()` outside
FastAPI dependencies. Connections are initialized and closed by the application
lifespan; repository mutations use Tortoise transactions.

## Creating migrations

After editing a model, generate a migration against an initialized development
database:

```sh
task py:migrate -- "add_creation_tag_to_group_preferences"
uv run aerich upgrade
```

Aerich reads `mealie.db.db_setup.TORTOISE_ORM`, configured in `pyproject.toml`.
Review generated SQL and test upgrade and downgrade on both SQLite and PostgreSQL.
Database changes do not require changes to the public Pydantic schemas unless the
HTTP API itself changes.

The Aerich history starts with a fresh schema. An existing database initialized
with Alembic cannot be upgraded in place through this history. Historical migration
sources are retained under `tests/fixtures/legacy_migrations/` solely for regression
tests; the application does not import or execute them.

## Tests

Run the backend suite with one worker per group of test files:

```sh
uv run pytest -n 4 --dist loadfile
```

Each worker owns its database. Synchronous test setup uses
`tests.fixtures.fixture_database.run_db()` to run native async database operations
on the TestClient's application loop. Async tests use `await_db()` for the same
purpose. This keeps PostgreSQL pools and SQLite connection locks on their owning
event loop while preserving the synchronous HTTP test client.
