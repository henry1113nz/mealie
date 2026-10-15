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
As part of this stage, preserve the recipe/ingredient database invariants that Tortoise
model metadata cannot declare:

- Add database CHECK constraints to `ingredient_foods_substitutions` for
  `food_id != substitute_food_id` and
  `substitute_food_id IS NOT NULL OR note IS NOT NULL`.
- Add a database CHECK constraint to `recipes_ingredients_substitutions` for
  `substitute_food_id IS NOT NULL OR note IS NOT NULL`.
- Preserve PostgreSQL `pg_trgm` and GIN indexes for every normalized recipe,
  ingredient, food, unit and alias column that has a corresponding legacy trigram
  index. Keep ordinary SQLite indexes as defined by the Tortoise fields.
- Preserve alias logical keys `(id, owner_id)` for `ingredient_foods_aliases` and
  `ingredient_units_aliases` with a hidden ORM surrogate primary key plus a database
  `UNIQUE (id, owner_id)` constraint. Keep the existing UUID `id` and owner foreign
  key columns and their names. The legacy UUID `id` remains UUID-valued, non-null,
  and generated by its existing UUID default, but is no longer the ORM primary key;
  only the new internal integer surrogate is the ORM and database primary key. This
  adds an internal integer column to each alias table; it does not change the public
  Pydantic schemas or alias API.

Implement these as explicit Aerich SQL migration operations after the model-created
tables exist. Aerich migration functions return SQL from `upgrade(db)` and
`downgrade(db)`; use dialect-specific statements where needed. The migration must be
ordered after the initial model baseline and before any application cutover. The
Stage 15 startup switch, default data seeding, complete model-graph baseline review,
Alembic boundary documentation, and unrelated PostgreSQL/schema operations remain
deferred. Do not use application-only validation as a replacement for DB constraints.

SQLite does not support `ALTER TABLE ... ADD CONSTRAINT`. The SQLite upgrade must
use a supported table-rebuild strategy (or an equivalent supported approach) to add
the substitution CHECK constraints. The rebuild must preserve existing row data,
foreign keys, indexes and uniqueness, and restore SQLite foreign-key enforcement on
success and failure. Its downgrade must remove only the Stage 4 checks and restore
the prior table shape while preserving the same data and other constraints. Test
both upgrade and downgrade against populated databases, then verify `PRAGMA
foreign_key_check`, table/index metadata and rejection/acceptance cases. PostgreSQL
upgrade and downgrade must likewise preserve existing rows, FKs and unrelated
indexes/constraints.

Focused acceptance checks must initialize a clean database and execute the actual
ordered Aerich migration path from the initial schema through the Stage 4 custom
migration before fixture data is inserted. Do not test only extracted SQL or a
test-only approximation. Exercise upgrade and downgrade through Aerich on populated
SQLite data; run the same ordered migration path on PostgreSQL when available.

Acceptance: model discovery and isolated SQLite schema, CRUD, relation-loading and
ordering checks pass; database-level checks reject both invalid substitution forms;
alias tests prove duplicate `(id, owner_id)` pairs fail and the same `id` under
different owners succeeds, with lookups/updates/deletes scoped to the intended row.
Compare mapped columns, foreign keys, indexes and constraints against the legacy
schema, explicitly accounting for the new hidden alias surrogate column. PostgreSQL
verification must separately confirm `pg_trgm` extension presence, each expected GIN
index's existence and validity, and that the indexed fuzzy-search operator can use
the index. Do not require planner selection on a tiny fixture dataset, where a
sequential scan can be cheaper. If no PostgreSQL test server is available, mark that
criterion not verified and the stage incomplete. Keep the full required pytest
command and record its result after the focused checks pass.

Stage 4 implementation notes (2026-10-14): Tortoise mappings for recipe core,
nutrition, ingredient, food, unit, alias, substitution and household-food link
models are present in `mealie/db/tortoise_models/`. SQLite schema/CRUD/relation
ordering passed outside the sandbox; the full suite passed with 3178 passed and
18 skipped. Follow-up probes confirmed that the current schema accepts invalid
substitution rows and rejects a repeated alias UUID under a different owner.
PostgreSQL was not verified. The custom schema work added to Stage 4 above is
therefore still required before this stage is complete. Recipe links to
organizers, meal plans, sharing, comments, timeline and later domains remain
out of this stage.

Stage 4 PostgreSQL verification update (2026-10-14; supersedes the earlier
PostgreSQL-not-verified status above): Against only the dedicated
PostgreSQL 16 `stage4_test` database, the bounded command
`UV_CACHE_DIR=/tmp/uv-cache timeout 180s uv run python
/tmp/stage4_postgres_acceptance.py` (exit 0) confirmed a clean Aerich baseline,
the ordered Stage 4 upgrade/downgrade, all three validated CHECK constraints
and rejection cases, alias pair uniqueness and row-scoped update/delete, and
all 12 expected `pg_trgm` GIN indexes present, valid, ready, and defined with
`gin_trgm_ops`. A populated fuzzy-search query returned matches, and `EXPLAIN`
with `SET LOCAL enable_seqscan = off` used
`ix_recipes_name_normalized_gin`; this demonstrates index usability without
requiring planner selection on a small dataset. The post-test baseline tables
were removed from the dedicated database after verifying the exact table
inventory; `pg_trgm` remains installed. The SQLite migration checks and full
suite previously passed (2 focused tests; 3179 passed, 18 skipped). No
implementation files changed during this PostgreSQL verification.

### Stage 5 — Remaining model graph
Complete organizers, meal plans, shopping lists, ratings, events, tokens, server records
and remaining association tables. Resolve cross-domain references. Move the ordered
Aerich model baseline and the Stage 4/Stage 5 schema operations needed for this model
graph forward from Stage 15. Stage 15 still owns application startup cutover, default
data seeding and the deployment boundary; none of those are part of this stage.

Before generating the Aerich baseline, correct the five non-alias composite-key model
mappings below so their former key tuples, rather than `id` alone, remain the logical
database identity. The baseline must include the Tortoise surrogate mappings and
legacy uniqueness described here. Apply the ordered migrations on a clean database in
this order: full model baseline, existing Stage 4 invariant migration, then the Stage 5
cyclic-FK migration. Do not defer any Stage 5 constraint or key behavior to Stage 15.

The Stage 5 migration must add database-enforced foreign keys and Tortoise relation
access for these four legacy references. Their target column is `id` in every case;
all source columns are nullable UUIDs, and the legacy foreign keys specify no delete
action, which means `NO ACTION` (the database default):

| Source column | Target column | Nullable | Delete action | Tortoise relation |
| --- | --- | --- | --- | --- |
| `ai_provider_settings.default_provider_id` | `ai_providers.id` | yes | `NO ACTION` | `AIProviderSettings.default_provider` |
| `ai_provider_settings.audio_provider_id` | `ai_providers.id` | yes | `NO ACTION` | `AIProviderSettings.audio_provider` |
| `ai_provider_settings.image_provider_id` | `ai_providers.id` | yes | `NO ACTION` | `AIProviderSettings.image_provider` |
| `users.owned_recipes_id` | `recipes.id` | yes | `NO ACTION` | `User.owned_recipes` |

The three provider references form cycles with `ai_providers.settings_id`; the User
reference targets `recipes`, which already references users. Create the referenced
tables first, then add these four constraints in ordered Aerich DDL. Preserve the
legacy column names, UUID type, nullability and indexes. The Tortoise relations must
support async relation loading as well as writes through the corresponding relation
or ID field. A scalar UUID field without a database FK is not sufficient.

Tortoise has one primary key per model. For each of these five legacy composite
primary-key tables, use an internal surrogate primary key and a database `UNIQUE`
constraint on the exact former tuple. Do not make the legacy UUID `id` column unique
unless the legacy schema did so. Keep every existing column, foreign key, default and
nullability unchanged; in particular keep the generated UUID default on `id` and the
original non-null key-component columns. Preserve all non-key field defaults and
nullability as well:

| Table | Legacy composite primary-key tuple | Other defaults/nullability to preserve |
| --- | --- | --- |
| `households_to_recipes` | (`id`, `household_id`, `recipe_id`) | `id` UUID generated by `GUID.generate`; `last_made` nullable with no default |
| `shopping_list_item_recipe_reference` | (`id`, `shopping_list_item_id`) | `id` UUID generated by `GUID.generate`; `recipe_id` nullable; `recipe_quantity` non-null; `recipe_scale` default `1`; `recipe_note` nullable |
| `shopping_list_recipe_reference` | (`id`, `shopping_list_id`) | `id` UUID generated by `GUID.generate`; `recipe_id` nullable; `recipe_quantity` non-null |
| `shopping_lists_multi_purpose_labels` | (`id`, `shopping_list_id`, `label_id`) | `id` UUID generated by `GUID.generate`; `position` non-null with default `0` |
| `users_to_recipes` | (`id`, `user_id`, `recipe_id`) | `id` UUID generated by `GUID.generate`; `rating` nullable; `is_favorite` non-null |

Inspect all incoming foreign-key references to these five tables before choosing the
surrogate DDL; record the findings and ensure no referencing constraint loses its
target semantics. Verify create, lookup, update and delete operations scoped by the
surrogate key, and verify duplicate former tuples are rejected while distinct tuples
that share only `id` remain allowed, matching the former composite key. The Stage 4
alias tables are excluded from this list: retain their already-approved hidden
surrogates and `(id, owner_id)` uniqueness.

Twelve legacy keyless association tables receive an internal auto-generated integer
surrogate primary-key column so Tortoise can register and address each row. The new
column is an internal schema addition; keep all legacy columns, their nullable/default
properties, foreign keys and pair uniqueness. In particular, do not add uniqueness
beyond these existing pairs, and preserve the existing NULL behavior of SQL `UNIQUE`:

| Table | Surrogate column | Existing unique tuple |
| --- | --- | --- |
| `group_to_categories` | `row_id` | (`group_id`, `category_id`) |
| `plan_rules_to_categories` | `row_id` | (`group_plan_rule_id`, `category_id`) |
| `recipes_to_categories` | `row_id` | (`recipe_id`, `category_id`) |
| `cookbooks_to_categories` | `row_id` | (`cookbook_id`, `category_id`) |
| `recipes_to_tags` | `row_id` | (`recipe_id`, `tag_id`) |
| `plan_rules_to_tags` | `row_id` | (`plan_rule_id`, `tag_id`) |
| `cookbooks_to_tags` | `row_id` | (`cookbook_id`, `tag_id`) |
| `households_to_tools` | `row_id` | (`household_id`, `tool_id`) |
| `recipes_to_tools` | `row_id` | (`recipe_id`, `tool_id`) |
| `cookbooks_to_tools` | `row_id` | (`cookbook_id`, `tool_id`) |
| `plan_rules_to_households` | `row_id` | (`group_plan_rule_id`, `household_id`) |
| `households_to_ingredient_foods` | `id` | (`household_id`, `food_id`) |

These legacy pair constraints already prevent duplicate non-NULL pairs; the surrogate
must not turn previously permitted NULL-containing rows into rejected rows. Verify
that all twelve legacy FK sets remain enforced and that row-level updates/deletes use
the surrogate without changing or collapsing duplicate rows that were legal under
the legacy NULL/UNIQUE semantics.

Inspect the generated Aerich baseline source before importing it. The Stage 4
regression test currently fails while importing a generated migration: a reproduced
generated file contains `schema\/constraint fidelity` inside the triple-quoted SQL
at line 352.
Python reports `SyntaxWarning: "\\/" is an invalid escape sequence`; with this
repository's warnings-as-errors test configuration, migration import fails. The
source is the Tortoise-generated SQL comment from the `HouseholdIngredientFood` model
docstring. Repair the generated-source/comment escaping (or remove that nonessential
SQL comment at its source) without altering or weakening the test. Run
`tests/unit_tests/test_tortoise_stage4_migration.py` unchanged and require its full
existing upgrade, constraint, relation, downgrade and data-preservation assertions
to pass.

Focused verification must execute the actual ordered Aerich migrations (full model
baseline, Stage 4 migration, Stage 5 migration), not extracted SQL or a test-only
approximation. On both SQLite and PostgreSQL, test populated-database upgrade and
downgrade, row/data preservation, every FK's invalid-reference rejection, nullable
references, relation loading, the five surrogate-plus-unique key behaviors, and the
twelve keyless association tables' FK and exact uniqueness/NULL behavior. Verify
SQLite `PRAGMA foreign_key_check` and metadata after each direction. Verify PostgreSQL
constraint definitions and valid/ready indexes after each direction. If PostgreSQL
is unavailable, record it as not verified; do not claim Stage 5 complete.

Acceptance: all intended models register; the complete table, column, key, FK, index
and constraint inventory matches the legacy schema except for the explicitly
documented internal surrogate columns and the Stage 4 alias surrogate conversion.
All four cross-domain FKs and ORM relations behave as specified; all five former
composite key tuples and all twelve keyless association constraints preserve their
legacy behavior. Record every unavoidable difference and its compatibility impact.
Repair and pass the unchanged Stage 4 migration regression test. After all focused
checks pass, run the full required command `uv run pytest -n 4 --dist loadfile` and
record its result. Record PostgreSQL evidence separately; if unavailable, leave that
criterion not verified and Stage 5 incomplete.

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

### Stage 15 — Startup and seed cutover
Use the Aerich baseline and ordered schema migrations established in Stage 5. Configure
fresh-install lifecycle and switch startup/default seeding only once required runtime
consumers are compatible. Keep unsupported in-place Alembic upgrades explicitly out
of scope; document the new-database/upgrade boundary here.
Acceptance: fresh SQLite initialization and repeated startup are idempotent; default
records are correct; connections close cleanly. PostgreSQL startup behavior remains
separately evidenced or explicitly not verified.

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
