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

Each numbered stage is one implementation session. The six-hour budget is shared
across planning and implementation; it is not six hours per stage. Completing all
stages is not assumed. If a stage cannot meet its acceptance criteria within the
session, stop and record the unfinished work and blockers.

### Verification rules for every stage

- Implement only the named stage and its necessary setup/access adaptations.
- Keep existing tests, assertions, expected values and skip/xfail markers intact.
- Adapt test database access alongside each converted feature rather than postponing
  all fixture work until the end.
- Before running focused tests, identify existing test files in the repository and
  record their exact paths. Use:
  `uv run pytest -n 4 --dist loadfile <existing-test-paths>`
- At the end of each stage, run the full measurement through the evidence repository.
  Record the commit, focused-test results, full-suite results, mypy results and test
  integrity counts. Never describe focused checks as proof that the whole app works.
- Mark each criterion as met, not met or not verified. A failed relevant test means
  its criterion is not met. Unavailable PostgreSQL checks are not verified.
- Preserve public HTTP contracts and Pydantic fields, aliases, validators and expected
  behavior. ORM loading helpers may be adapted without changing public schema contracts.
- Retain legacy runtime paths until their replacement and callers are ready. Temporary
  coexistence must not split one operation across inconsistent database state or
  transaction boundaries.

### Stage 1 — Dependencies and isolated async database lifecycle
Add compatible Tortoise/Aerich and driver dependencies, SQLite/PostgreSQL configuration,
and isolated initialization/shutdown helpers. Do not switch application startup,
remove legacy initialization, or introduce a production placeholder model.
Acceptance: dependency installation succeeds; both configurations can be constructed;
an isolated SQLite smoke check connects, queries and closes successfully. Record
PostgreSQL smoke results separately. Existing application tests remain unchanged.

### Stage 2 — Test lifecycle support for incremental migration
Establish how converted tests and FastAPI TestClient share correctly owned connections,
event loops and worker-specific databases. Add only the necessary fixture support;
retain existing initialization for tests that still use SQLAlchemy.
Acceptance: existing fixture consumers still work; worker database isolation is
preserved; an async database smoke check runs through the intended fixture lifecycle.
No assertions or test expectations are changed.

### Stage 3 — Group, household and user model definitions
Introduce Tortoise mappings for these domains and their required relations, preserving
table names, keys, defaults, uniqueness and tenant boundaries. Keep legacy callers
working until their later conversion.
Acceptance: model discovery succeeds; isolated SQLite schema and CRUD/relationship
checks pass; mapped constraints are documented and PostgreSQL status is recorded.

### Stage 4 — Recipe core and ingredient model definitions
Map recipe core, ingredients and required food/unit dependencies, including ordering,
nullable fields, UUIDs and timestamps. Do not switch recipe routes yet.
Acceptance: discovery and isolated relation/ordering checks pass; compare mapped
columns and constraints with the existing schema. Record unresolved behavior explicitly.

### Stage 5 — Remaining model graph
Complete organizers, meal plans, shopping lists, ratings, events, tokens, server records
and remaining association tables. Resolve cross-domain references.
Acceptance: all intended models register; compare the complete table/constraint
inventory with the current schema. Do not equate model registration with runtime
migration. Record exact discrepancies and PostgreSQL-specific requirements.

### Stage 6 — Shared async repository primitives
Implement async CRUD, transaction handling, tenant scoping and explicit serialization
loading for the new persistence path, without prematurely switching every caller.
Acceptance: focused tests cover CRUD, rollback, group/household isolation and relation
materialization. Existing legacy callers remain usable.

### Stage 7 — Filtering, sorting and pagination
Implement the existing query-filter language and pagination semantics for Tortoise,
including nested conditions, relationship fields, null ordering and counts.
Acceptance: existing pagination/filter tests pass with unchanged expectations after
necessary database-access adaptations; record exact test paths and backend differences.

### Stage 8 — Authentication and user operations
Convert user repositories, authentication dependencies, registration and password
reset together with their callers and required tests.
Acceptance: relevant login, permission, registration and password-reset tests pass;
response contracts and tenant isolation remain unchanged; async calls are awaited.

### Stage 9 — Group and household operations
Convert repositories, services and routes for group/household settings, invitations,
organizers and administrative operations.
Acceptance: focused group/household and permission tests pass with unchanged expected
values; no converted operation silently falls back to a legacy session.

### Stage 10 — Recipe read operations
Convert recipe lookup, listing, sharing and read serialization using the shared query
machinery and explicit relation loading.
Acceptance: focused recipe read/search/share tests pass; pagination, scoping and
response fields are preserved. PostgreSQL fuzzy-search checks are recorded separately.

### Stage 11 — Recipe write operations
Convert creation, updates, deletion, ingredient handling and associated organizer writes.
Acceptance: relevant CRUD and relation tests pass; atomic updates, ordering and cascade
behavior are preserved, including rollback on failed writes.

### Stage 12 — Meal plans, cookbooks and shopping lists
Convert their repositories, services and routes with the required database test access.
Acceptance: relevant domain and tenant-boundary tests pass. If this scope proves too
large, stop and revise the plan in a separate commit before splitting it further.

### Stage 13 — Remaining services, routes and import workflows
Audit remaining database callers, including parser, bulk actions, AI-provider operations,
SPA reads and import/export workflows. Convert unresolved runtime paths.
Acceptance: list every remaining caller and its disposition; relevant existing tests
pass and public schema contracts remain unchanged. Do not claim completeness from
direct-import scans alone.

### Stage 14 — Scheduler, event bus and scripts
Convert DB-backed tasks, event subscriptions/publishing and operational scripts together
with affected callers. Keep connection and event-loop ownership explicit.
Acceptance: relevant scheduler/event tests pass; script smoke results are recorded;
no unawaited DB coroutine or legacy session remains in the converted paths.

### Stage 15 — Aerich baseline, startup and seed cutover
Generate the full initial schema migration, configure fresh-install lifecycle, and
switch startup/default seeding only once required runtime consumers are compatible.
Keep unsupported in-place Alembic upgrades explicitly out of scope.
Acceptance: fresh SQLite initialization and repeated startup are idempotent; default
records are correct; connections close cleanly; PostgreSQL extensions/indexes and
migration behavior have evidence or remain explicitly not verified.

### Stage 16 — Backup and restore
Replace SQLAlchemy reflection/export/restore assumptions and define legacy-backup
compatibility without silently changing the public API.
Acceptance: relevant backup round-trip, datetime and invalid-FK tests pass; foreign-key
enforcement is restored after errors. Record both backend results separately.

### Stage 17 — Full integration and test-fixture audit
Finish remaining database-access fixture adaptations and audit all runtime call chains.
Run `uv run pytest -n 4 --dist loadfile` and `uv run mypy mealie`.
Acceptance: no unexplained failures/errors; no tests or assertions removed or weakened;
no new skip/xfail markers; worker isolation remains correct. Record missing backend
verification explicitly.

### Stage 18 — Legacy removal and final audit
Remove SQLAlchemy/Alembic runtime dependencies, obsolete model helpers/history and
configuration only after their callers are replaced.
Acceptance: no Python imports SQLAlchemy anywhere under mealie/; installation,
full pytest and mypy succeed after cleanup; fresh SQLite/PostgreSQL lifecycle and
backup/restore meet the completion gate. Text mentions in documentation are assessed
separately from executable imports.

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

## Review notes

This revision was drafted with ChatGPT assistance at the participant's request.
It must not be reported as an unaided human review. The participant should read
the revised stages and record whether they accept them before implementation.

Changes and reasons:
- Split broad model/repository/service stages into smaller numbered sessions.
- Added early incremental test-lifecycle support because earlier acceptance criteria
  depended on fixtures that the original plan postponed until Stage 9.
- Deferred application startup cutover and legacy removal until dependent callers
  are ready, reducing the risk of breaking still-synchronous runtime paths.
- Required recorded existing test paths and separated focused tests, full measurement,
  and PostgreSQL verification. Missing evidence does not count as a pass.
- Clarified preservation of public Pydantic contracts while adapting internal ORM bridges.
- Added an explicit stop/revision rule when a stage is too large and clarified that
  the total budget includes planning. Stage sizes remain estimates.
- Preserved the original dependency inventory and risk section; their exhaustive
  accuracy has not been independently verified against the complete source tree.
