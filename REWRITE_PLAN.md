# SQLAlchemy to Tortoise ORM Migration Plan

## Scope and fixed constraints

- Replace SQLAlchemy with async Tortoise ORM throughout `mealie/`; after completion no Python module under `mealie/` imports SQLAlchemy.
- Preserve the HTTP API and every Pydantic schema in `mealie/schema` (no frontend type or behavior changes).
- Support SQLite and PostgreSQL, including the current database features that differ by dialect.
- Replace Alembic with Aerich. Existing databases are not upgraded from their Alembic history; document the new-database/upgrade boundary clearly.
- Convert database access, routes, services, scheduler jobs, scripts and application lifecycle to async as needed.
- Keep all tests and assertions. Test database setup/access may change. Run the requested suite as `uv run pytest -n 4 --dist loadfile` when implementation is complete.

## SQLAlchemy dependency inventory

The named packages contain both direct ORM imports and indirect assumptions such as lazy relationship loading, mutable identity maps, synchronous session methods, ORM expression objects in schemas, and query composition. Inventory by package:

### `mealie/db`

- `db_setup.py`: synchronous engine/sessionmaker/context managers; engine connect listeners configure SQLite WAL and test pragmas.
- `init_db.py`: Alembic startup/head checks, sync connection check, extension setup, data fixes, and synchronous default group/household/user initialization.
- `fixes/fix_group_with_no_name.py`, `fixes/fix_migration_data.py`: synchronous ORM queries, writes, commits, metadata table access and migration repair logic.
- `models/_model_base.py`, `_filterable_column.py`, `_model_utils/{auto_init,datetime,guid}.py`: declarative base, mapped columns, synonyms, SQLAlchemy types, dialect conversion and model construction conventions.
- All model modules under `models/group/`, `models/household/`, `models/recipe/`, `models/server/`, and `models/users/`: declarative mappings, foreign keys, relationships/cascades, association tables/proxies, query expressions, validators, ORM events, ordering lists, and constructors that accept a session. Highest-complexity examples are `recipe/recipe.py`, `recipe/ingredient.py`, `recipe/category.py`, `recipe/tag.py`, `recipe/tool.py`, `group/ai_providers.py`, and `household/shopping_list.py`.
- `models/__init__.py`, `_all_models.py`, and domain `__init__.py` modules aggregate/register the model graph and must be adapted for Tortoise app discovery.

### `mealie/repos`

- `repository_generic.py`: generic CRUD, pagination, sorting, filtering, count, and transaction behavior expressed through SQLAlchemy `Select`, `ColumnElement`, `Session`, result objects and ORM identity state.
- `repository_factory.py`, `all_repositories.py`: session-bound repository construction, dialect inspection, SQL expression helpers and repository wiring.
- Specialized query and write implementations: `_recipe_suggestions.py`, `_utils.py`, `repository_ai_provider.py`, `repository_cookbooks.py`, `repository_foods.py`, `repository_group.py`, `repository_household.py`, `repository_meal_plan_rules.py`, `repository_meals.py`, `repository_recipes.py`, `repository_shopping_list.py`, `repository_units.py`, and `repository_users.py`.
- Preserve repository scoping by group and household, ordering/pagination semantics, eager-loading needed for serialization, cascade behavior, and commit/rollback boundaries.

### `mealie/services`

- Database-coupled group, household and recipe services: `group_services/{group_service,labels_service}.py`, `household_services/{household_service,shopping_lists}.py`, `recipe/recipe_service.py`, and `user_services/{password_reset_service,registration_service}.py`.
- Scheduler tasks with direct database scopes: all files in `scheduler/tasks/` (timeline event creation, checked shopping item deletion, webhooks, share-token/export/password-reset/registration purges, and locked-user reset); update scheduler callback wrappers to await async tasks.
- Event listeners and API handlers: `event_bus_service/{event_bus_listeners,event_bus_service}.py`; listener sessions and request dependencies become async.
- Database shape/query dependencies: `query_filter/builder.py`, `parser_services/{_base,ingredient_parser}.py`, and `migrations/utils/database_helpers.py` (the latter concerns importing recipe data and may use model/repository APIs).
- Backup and restore: `backups_v2/alchemy_exporter.py`, `backup_file.py`, `backup_v2.py`; exporter name, reflection, table access, Alembic version payload, restore ordering, foreign-key disabling and restore initialization all currently encode SQLAlchemy/Alembic assumptions. Preserve the public backup format/API as applicable or explicitly version it without changing route schemas.
- The remaining services mostly use repositories indirectly; async propagation must be audited transitively through `BaseService`, import workflows, organizer resolution, seeding, export, and backup callers.

### `mealie/routes`

- Shared database injection and controller/mixin infrastructure: `routes/_base/base_controllers.py`, `routes/_base/mixins.py`, and request-scoped `generate_session` consumers.
- Direct repository/session access in route groups: `admin/admin_management_ai_providers.py`, `admin/admin_management_households.py`, `admin/admin_management_users.py`, `app/app_about.py`, `auth/auth.py`, `groups/controller_migrations.py`, `households/controller_cookbooks.py`, `households/controller_mealplan.py`, `organizers/controller_categories.py`, `parser/ingredient_parser.py`, `recipe/_base.py`, `recipe/recipe_crud_routes.py`, `recipe/shared_routes.py`, `recipe/timeline_events.py`, `users/forgot_password.py`, `users/ratings.py`, `users/registration.py`, and `validators/validators.py`.
- `routes/spa/__init__.py` performs DB-backed shared recipe HTML/meta lookups. Other route modules may consume DB-backed dependencies without importing SQLAlchemy directly; audit the complete `mealie/routes/` tree during propagation.
- FastAPI dependency providers, authentication dependencies and Pydantic response serialization must not trigger sync DB access or unloaded async relations.

### `mealie/schema`

Schema definitions must remain unchanged in shape, fields, aliases, validators and HTTP behavior. Current SQLAlchemy coupling is concentrated in ORM-aware serialization and loading:

- `schema/_mealie/mealie_model.py` bridges ORM objects into Pydantic.
- `schema/user/user.py` and `user_passwords.py` import joined/select-in loader options and loader-option typing.
- ORM-backed schema conversion/query helpers occur in `cookbook/cookbook.py`, `group/ai_providers.py`, `household/{group_events,group_shopping_list,household,household_preferences}.py`, `meal_plan/{new_meal,plan_rules}.py`, `recipe/{recipe,recipe_category,recipe_comments,recipe_ingredient,recipe_share_token,recipe_timeline_events,recipe_tool}.py`, `reports/reports.py`, `response/query_search.py`.
- Replace only the ORM bridge and loading declarations needed for Tortoise. Avoid changing the externally visible Pydantic models; materialize relation data before validation where Tortoise async relations require it.

### `mealie/alembic`

- `alembic.ini`, `env.py`, `script.py.mako`, and all files in `versions/` are Alembic migration configuration/history, including dialect-specific DDL and historical data migrations. They are replaced by Aerich configuration and a fresh initial migration/model baseline; no Alembic-to-Aerich history conversion is required.
- Preserve current schema constraints/indexes/data invariants in the Aerich baseline and follow-up migrations. Inspect all historical migrations as a specification, especially PostgreSQL `pg_trgm`/GIN search support, normalization, foreign keys/cascades, uniqueness, backfills and newer recipe/household fields.

### Test database setup: `tests/conftest.py` and `tests/fixtures/`

- `tests/conftest.py`: xdist worker-specific SQLite data directories and PostgreSQL database creation currently use SQLAlchemy engine/text; session-scoped app dependency override uses `SessionLocal`; `main()` initializes DB before fixtures.
- `fixture_database.py`: module-scoped synchronous `SessionLocal`, repository factory fixture and unfiltered DB.
- `fixture_admin.py`, `fixture_multitenant.py`, `fixture_users.py`: synchronous Session annotations and repository construction/mutations across fixture setup/teardown.
- `fixture_recipe.py`, `fixture_shopping_lists.py`: SQLAlchemy exceptions, ORM refresh/expire and relationship/cascade assumptions.
- `tests/fixtures/__init__.py` and all fixture modules must work with async ORM initialization and the existing TestClient pattern. Keep test file grouping with `--dist loadfile`; do not remove tests or weaken assertions.

### Adjacent `mealie/` dependencies required by the no-import rule

- `mealie/core`: DB-backed auth/dependency lookups in `dependencies/dependencies.py`, `exceptions.py`, `security/security.py`, and `security/providers/{auth_provider,credentials_provider,ldap_provider,openid_provider}.py`.
- `mealie/scripts/reprocess_images.py` plus other scripts that use `session_context()` (for example password/admin/reset scripts) need async entry points and Tortoise lifecycle management.
- `mealie/services/backups_v2/alchemy_exporter.py` is covered above. Remove SQLAlchemy/Alembic runtime dependencies from `pyproject.toml`, Ruff's third-party configuration and Taskfile commands once all callers are migrated.
- Search the whole `mealie/` tree, not only the named folders, for imports and SQLAlchemy type references before declaring completion.

## Staged execution plan

Each stage is sized as a separate implementation session. Complete the prior stage and its acceptance checks before starting the next, so the running application remains diagnosable.

### Stage 1 — Define async persistence contract and dependencies

Add pinned Tortoise ORM and Aerich dependencies, configure Tortoise app/model discovery, SQLite and async PostgreSQL driver URLs, lifecycle ownership, and a small database abstraction for initialization/shutdown and transaction boundaries. Decide how table/column names, UUID representation, timestamps, nullable values, JSON fields, defaults, indexes and constraints map. Keep existing SQLAlchemy available temporarily while the conversion proceeds.

**Acceptance criteria and evidence:** Settings can construct both SQLite and PostgreSQL Tortoise configurations; a minimal app lifespan initializes/closes connections; a temporary database can create/read a minimal model on SQLite. A focused DB bootstrap test passes. PostgreSQL smoke evidence is recorded when a test service is available.

### Stage 2 — Convert model graph and establish schema baseline

Convert the declarative model graph in `mealie/db/models/` to Tortoise models and fields. Rebuild FK/M2M relations, through tables, unique constraints, indexes, ordering, cascade rules, timestamp and normalization behavior, computed/search-only fields, and model initialization helpers. Remove ORM events/proxies by moving behavior into explicit async services/repositories. Generate the Aerich initial migration from the complete model graph and compare the schema against current Alembic head specifications.

**Acceptance criteria and evidence:** Model import/discovery succeeds without SQLAlchemy models; Aerich can initialize an empty SQLite database and a PostgreSQL database and produce equivalent table/constraint structure for portable features. Model-focused tests pass, including ingredient substitutions, recipe organizer relations, cascades, timestamps and defaults. PostgreSQL-specific search extensions/indexes have explicit migration coverage.

### Stage 3 — Replace DB startup, fixes, and migration lifecycle

Replace `db_setup.py` and `init_db.py` with async Tortoise lifecycle, connectivity retry, Aerich upgrade-to-head, PostgreSQL extension setup, initialization of default group/household/user, and async data repair functions. Specify fresh-install behavior and that legacy Alembic upgrade is unsupported. Replace `mealie/alembic/` runtime/config with Aerich migration configuration and new migrations; remove old history after callers are switched.

**Acceptance criteria and evidence:** Fresh SQLite and PostgreSQL startup creates schema, applies the Aerich baseline, creates default records exactly once, reruns idempotently, and closes connections cleanly. Existing initialization/data-fix tests pass or are adapted only in setup/API mechanics without changing assertions. No startup path imports Alembic or SQLAlchemy.

### Stage 4 — Migrate generic repositories and query/filter machinery

Rewrite repository construction and generic CRUD in `repos/`, beginning with common scoping, create/update/delete, pagination, sorting, search/filter, count and serialization/eager loading. Replace SQLAlchemy query expressions and dialect inspection with Tortoise QuerySets/Q objects/expressions or explicit backend-specific SQL where necessary. Preserve transactions and group/household isolation.

**Acceptance criteria and evidence:** Generic repository and API CRUD/search/pagination tests pass with unchanged expected values on SQLite. Tenant-boundary tests pass. PostgreSQL query/search tests pass when available. Static scan shows the migrated generic repository/query helper layer has no SQLAlchemy imports.

### Stage 5 — Migrate specialized repositories and model-dependent serialization

Convert every specialized repository (`repository_factory.py`, `all_repositories.py`, all listed repository modules, `_recipe_suggestions.py`) and relation-heavy schema conversion paths. Use explicit prefetch/select-related plans and build unchanged schema objects after awaiting relations. Handle database-specific fuzzy search and bulk update/delete semantics.

**Acceptance criteria and evidence:** Repository tests across recipes, ingredients/units/foods, users/ratings, meal plans, cookbooks, shopping lists, organizers, AI providers and groups pass. Serialization tests confirm API payloads stay byte/field-equivalent where asserted. Multi-tenant tests and PostgreSQL fuzzy-search behavior pass.

### Stage 6 — Propagate async through services, routes, auth and dependencies

Convert service methods and their callers to async wherever they touch repositories. Convert controller base classes, HTTP routes, validators, auth/security dependencies, event bus DB handlers and SPA shared-recipe lookups. Ensure async ORM access is awaited before returning Pydantic models or scheduling background work. Preserve response codes, route schemas and dependency overrides.

**Acceptance criteria and evidence:** Route/API tests pass with unchanged status codes, payloads and validation expectations; auth, registration, password reset, household switching and public/shared recipe tests pass. FastAPI reports no un-awaited coroutines or lazy relation access errors. `mealie/schema` public definitions remain unchanged.

### Stage 7 — Convert scheduler tasks, events, and operational scripts

Make all DB-using scheduler tasks async, update task registration/wrappers to await them, and migrate event listener lifecycle. Convert scripts, seeding and import utilities that currently open sync sessions. Ensure one event loop owns Tortoise connections and task invocations close scopes correctly.

**Acceptance criteria and evidence:** Scheduler task unit/integration tests pass for each task; event bus tests pass; script smoke tests run against SQLite and applicable PostgreSQL setup. Scheduler logs/errors and task cadence remain unchanged. No `session_context()` or sync session APIs remain in runtime callers.

### Stage 8 — Replace backup/restore persistence path

Replace `AlchemyExporter` reflection, schema dump/restore and Alembic version restoration with a Tortoise-compatible backup implementation. Preserve backup data behavior and datetime/UUID/FK cleanup, including SQLite/PostgreSQL foreign-key handling and the existing datetime-column coverage. Define compatibility for legacy backup files carrying `alembic_version` separately from unsupported in-place Alembic database upgrades.

**Acceptance criteria and evidence:** Backup round-trip tests pass unchanged, including every datetime column and invalid-FK filtering; restore creates the Aerich schema then restores all rows and operational defaults. Test both SQLite and PostgreSQL, including FK enforcement restored after errors.

### Stage 9 — Convert test infrastructure and run full suite

Rewrite `tests/conftest.py` and `tests/fixtures/` for async Tortoise init/cleanup, per-worker DB isolation, async repository fixture access and relation refresh behavior. Preserve fixture scope semantics and all test bodies/assertions except necessary DB setup/access changes. Ensure PostgreSQL xdist worker database creation/drop uses a driver-compatible administrative connection. Run exactly `uv run pytest -n 4 --dist loadfile`; also run focused PostgreSQL coverage if configured.

**Acceptance criteria and evidence:** The full required command completes with all tests passing, no skips or xfails introduced and no tests deleted. Both SQLite and PostgreSQL suites/smokes pass where CI services exist. Xdist workers do not share databases; repeated module-scoped fixture use remains isolated as before.

### Stage 10 — Remove SQLAlchemy/Alembic remnants and final audit

Remove SQLAlchemy and Alembic dependencies/config, obsolete Alembic history, SQLAlchemy-only utility code, imports, typing, task commands and lint configuration. Update documentation and deployment configuration for Aerich startup and async DB lifecycle. Keep only explicit notes about the Alembic upgrade boundary.

**Acceptance criteria and evidence:** `rg -n -i 'sqlalchemy|alembic' mealie` returns no runtime imports/references (historical documentation may be clearly marked if retained); dependency lock/install resolves with Tortoise/Aerich only; the full test command passes after cleanup; startup, backup/restore and SQLite/PostgreSQL checks pass.

## Expected risks and mitigations

- **Async propagation breadth:** Repository calls are pervasive and often hidden behind auth dependencies, schema validators, service constructors, background tasks and scripts. Convert top-down in small slices; use type checking and un-awaited-coroutine warnings to find missed call sites.
- **Implicit ORM behavior:** SQLAlchemy identity maps, autoflush, lazy loading, relationship assignment, association proxies, ordering lists, events, `object_session`, query expressions and cascades have no automatic one-to-one translation. Make writes/loads explicit and test serialization, child ordering, aggregate updates and deletes.
- **SQLite differences:** Foreign keys are connection-scoped and must be enabled on every async connection; WAL and test pragmas need async-driver connection hooks. SQLite differs in DDL/ALTER support, booleans, UUID/date/time storage, JSON behavior, locking and concurrent writes. xdist workers need separate files and migrations must be tested from empty files.
- **PostgreSQL differences:** Use the async driver URL/driver supported by Tortoise. Preserve `pg_trgm`, GIN indexes, fuzzy search operators, schema/extension permissions, UUID and JSONB semantics, quoted identifiers and unique/FK constraints. Existing SQL sometimes branches on `session.get_bind()`; replace with deliberate backend-specific paths.
- **Transaction and consistency behavior:** SQLAlchemy methods commit at varied layers and often rely on session flush/rollback. Tortoise requires explicit transaction boundaries, especially nested recipe/ingredient/organizer updates, household moves, shopping-list operations, backup restore and data fixes.
- **Schema and migration drift:** Historical Alembic revisions contain data backfills as well as schema changes. The new Aerich baseline must represent the current intended schema, while necessary data invariants move into startup repair or one-time migration code. Existing Alembic databases will not be upgraded in place; communicate the new deployment path and avoid implying compatibility.
- **Backup contract:** Current backups encode `alembic_version`; changing schema management can break restore and external backup consumers even if the HTTP schemas remain stable. Version the internal backup payload deliberately and test old backup inputs if they remain supported.
- **Test process and lifespan:** `TestClient` runs an event loop/thread, while pytest fixtures and xdist have distinct lifetimes. Tortoise connections must initialize and close in the same lifecycle context; module/session-scoped synchronous fixtures may need async fixture or helper patterns without altering test assertions.
- **API/schema preservation:** ORM-aware Pydantic validation may currently fetch relations implicitly. Explicit async prefetch/materialization must keep every response field, null/default, alias, ordering and validation behavior unchanged.
- **Driver, packaging and deployment:** Aerich/Tortoise versions and async database drivers must match the supported Python version and lock/tooling. Docker, task commands, startup hooks and configuration must use the same database URL interpretation.

## Completion gate

The migration is complete only when the required xdist pytest command passes, SQLite and PostgreSQL paths have evidence, the external API and `mealie/schema` remain unchanged, Aerich replaces Alembic for new schema lifecycle, and a whole-tree scan confirms there are no SQLAlchemy imports anywhere under `mealie/`.
