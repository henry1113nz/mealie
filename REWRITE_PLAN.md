# Migration plan: SQLAlchemy to Tortoise ORM

Written in Workflow B, session s01, before any code changes. Starting point: `e365efc71`
(3177 tests pass, 0 mypy errors).

## 1. Where SQLAlchemy is used

| Package | Files importing SQLAlchemy | What depends on it |
|---|---|---|
| `mealie/db` | 43 | 56 models in 41 files, custom types (`GUID`, `NaiveDateTime`), `auto_init` (nested create/update from dicts), `FilterableColumn`, engine and session setup (`db_setup.py`), `init_db.py`, data fixes |
| `mealie/alembic` | 49 | 54 migrations; `init_db` runs them on start-up |
| `mealie/schema` | 20 | 18 schemas define `loader_options()` with `joinedload`/`selectinload`; `query_search.py` builds search SQL; `mealie_model.py` |
| `mealie/repos` | 14 | `RepositoryGeneric` (526 lines), recipe repository (451), recipe suggestions (402), users, foods/units merge, meal plans, cookbooks, households |
| `mealie/services` | 14 | query filter builder (717 lines), shopping lists, recipe service, event bus, scheduler tasks, migrations helpers, backups (`alchemy_exporter.py` exports and restores every table via metadata) |
| `mealie/routes` | 10 | base controllers and mixins (session per request, IntegrityError handling), auth, SPA, validators, a few routes with direct queries |
| `mealie/core` | 7 | `get_current_user` and auth providers (credentials, LDAP, OIDC) query users directly; exceptions |
| `mealie/scripts` | 1 | image reprocessing |
| `tests` | 25+ | `conftest.py` overrides `generate_session`; fixtures and many tests use sessions directly |

Session entry points: `generate_session` (FastAPI dependency) and `session_context()` (services,
scheduler tasks, scripts). All database access is synchronous; 327 route handlers are `def`, 23 are
`async def`.

## 2. Strategy

Run both ORMs against the same database and move one area at a time. A big-bang switch would leave
the suite red for the whole migration, which removes the only acceptance check we have. Coexistence
keeps the suite green after every stage and lets new code be compared with old code on the same data.

Before converting any area, record what the old ORM does without being asked, because none of it is
visible in the schema: relationship cascades and foreign-key nulling, lazy loading, `auto_init`
nested writes, filterable columns, association proxies (several `group_id`/`household_id`
attributes are proxies, so they affect permission scoping), and SQLite pragmas.

## 3. Stages

Every stage ends with `measure.sh`. Unless a stage says otherwise, every stage must also keep:
**0 failing tests, 0 mypy errors, test functions >= 1158, asserts >= 3837, skip markers <= 12, no
change to existing test assertions.**

| Stage | Work | Acceptance criteria (in addition to the above) |
|---|---|---|
| S1 Foundation | Add tortoise-orm and aerich. Tortoise models for all 68 tables with fields that store GUIDs and datetimes exactly like SQLAlchemy. Start Tortoise in the app lifespan and in tests. Match SQLite pragmas. | Every Tortoise model can query a database created by the existing migrations. A row written by Tortoise is read correctly by SQLAlchemy and the reverse. |
| S2 Implicit behaviour | Extract from the SQLAlchemy models: cascade/nulling on delete, relationship names, filterable columns, association proxies. Generic nested writes (replacing `auto_init`) and relation loading (replacing lazy loading). | A written inventory with counts. For one model of each kind (cascade, one-to-one, proxy-scoped) a test shows the Tortoise behaviour matches SQLAlchemy. |
| S3 Async data layer | Async generic repository with the same methods as `RepositoryGeneric`; async HTTP mixin; query filter on Tortoise (reuse the parser); ordering by related fields. | A differential test runs at least 25 filter strings through both builders on the same data and gets the same ids. A deliberately broken rule makes it fail. |
| S4 Group-level resources | Labels, reports, event notifiers, recipe actions, webhooks, AI providers, invite tokens. | Each resource's own tests pass when run alone, not only in the full suite. |
| S5 Organizers, foods, units | Tags, categories, tools, foods, units, including merge and alias logic. | Merge tests pass; differential check on organizer filters. |
| S6 Users and auth | `get_current_user`, credentials/LDAP/OIDC providers, tokens, password reset. | All auth and user tests pass. **Human review of every change before moving on (security).** |
| S7 Households, meal plans, cookbooks, shopping lists | Repositories and services in these areas. | Shopping list and meal plan tests pass alone and in the suite. |
| S8a Recipes: repository | Recipe CRUD, nested ingredients/steps/notes, share tokens, comments, timeline. | Recipe CRUD and bulk action tests pass. |
| S8b Recipes: search and suggestions | Normalized search, `column_aliases` (e.g. `last_made` per household), recipe suggestions. | Search and suggestion tests pass; differential check on search results. |
| S9 Background and admin | Scheduler tasks, event bus listeners, seeders, scripts, backups/restore (`alchemy_exporter`). | Backup/restore tests pass; a backup made before the stage restores after it. |
| S10 Remove SQLAlchemy | Move the filter parser out of `builder.py`; delete SQLAlchemy models, sessions and `loader_options`; replace Alembic with Aerich (initial migration from the Tortoise models); update test fixtures. | Nothing under `mealie/` imports SQLAlchemy. Full suite passes on SQLite and on PostgreSQL. |

## 4. Risks

1. **Async everywhere.** Tortoise is async-only; every route and service that touches the database
   has to become async. Mixing sync SQLAlchemy calls into async routes blocks the event loop during
   the migration.
2. **Two connections to one SQLite file.** Writes from one ORM can lock out the other; Tortoise's
   default `journal_mode=WAL` conflicts with Mealie's settings.
3. **Implicit behaviour lost silently.** Cascades, proxies and lazy loading do not raise errors when
   missing; they produce wrong data or wrong permission scoping. Tests may not cover every case.
4. **SQLite vs PostgreSQL.** SQLAlchemy does not enable foreign keys on SQLite; Tortoise does.
   GUIDs are stored differently (32-character hex vs native UUID). Tests run on SQLite only by
   default, so PostgreSQL differences can pass unnoticed until S10.
5. **Unsupported features.** Tortoise has no composite primary keys (7 tables), cannot index a
   `TextField`, and has no general `LIKE`.
6. **Test fixtures depend on SQLAlchemy.** Changing them is allowed but must not weaken tests;
   measure.sh tracks test functions, asserts and skip markers.
7. **Migrations.** Moving from Alembic to Aerich means existing databases cannot be upgraded through
   the old history (out of scope by the ground rules), but the first Aerich migration must match the
   schema the Alembic history produces.
8. **Size.** S8 and S10 are each larger than one session in practice; expect to split them further.
