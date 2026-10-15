# Stage 5 — Tortoise model inventory

## Registration and table coverage

`mealie.db.tortoise_models` registers 68 application models covering all 68
legacy SQLAlchemy tables. There are no missing or extra application table names.
The Aerich metadata table is separate and is not counted as an application table.
Tortoise initialization resolves the model references successfully. The registered
tables and the legacy column inventory were compared before implementation; no
legacy columns were missing.

All legacy unique constraints and single-column unique declarations are represented
by Tortoise fields or `unique_together`, including ingredient name/group uniqueness,
Stage 4 alias pairs, and keyless association pairs.

## Schema differences and migration behavior

- Twelve keyless association tables use an internal integer surrogate (`row_id`,
  except `households_to_ingredient_foods`, which uses `id`). Their legacy columns,
  nullable properties, foreign keys and pair uniqueness remain. SQLite tests preserve
  SQL `UNIQUE` NULL behavior by confirming duplicate `(NULL, NULL)` rows survive.
- Five non-alias composite-primary-key tables use an internal `row_id` primary key.
  The exact former tuples remain database unique constraints:
  `households_to_recipes` (`id`, `household_id`, `recipe_id`),
  `shopping_list_item_recipe_reference` (`id`, `shopping_list_item_id`),
  `shopping_list_recipe_reference` (`id`, `shopping_list_id`),
  `shopping_lists_multi_purpose_labels` (`id`, `shopping_list_id`, `label_id`),
  and `users_to_recipes` (`id`, `user_id`, `recipe_id`). The generated UUID default on
  legacy `id` and other defaults/nullability are retained; `id` is not independently
  unique. Existing alternate unique pairs remain. The two Stage 4 alias tables retain
  their approved hidden `row_id` and `(id, owner_id)` uniqueness.
- Four nullable cyclic references are represented as Tortoise relations with
  `db_constraint=False` during baseline generation. Ordered Stage 5 Aerich DDL adds
  `NO ACTION` database constraints from
  `ai_provider_settings.default_provider_id`, `audio_provider_id`, and
  `image_provider_id` to `ai_providers.id`, and from `users.owned_recipes_id` to
  `recipes.id`. Async relation loading and assignment use the legacy columns.
- The three Stage 4 substitution CHECK constraints remain explicit migration SQL:
  `ingredient_foods_substitutions_no_self_substitution`,
  `ingredient_foods_substitutions_food_or_note`, and
  `recipes_ingredients_substitutions_food_or_note`.

## Verification

Focused SQLite checks execute the full Aerich baseline followed by Stage 4 and Stage 5
migrations in order. The unchanged Stage 4 migration regression passes. Stage 5 checks
preserve rows and indexes, reject invalid references for all four cross-domain FKs,
load and clear nullable relations, preserve the five logical key tuples and existing
alternate pairs, and verify all twelve association FK/pair/NULL behaviors. The test
checks SQLite FK metadata and `PRAGMA foreign_key_check` after upgrade and downgrade.

The full required suite passes: `uv run pytest -n 4 --dist loadfile` (3180 passed,
18 skipped). Existing skips are recorded by pytest and were not introduced by Stage 5.

PostgreSQL Stage 5 acceptance passed against the user-designated `stage4_test`
database at `127.0.0.1:15432`. Before migrations, the identity query confirmed
database `stage4_test`, role `stage4`, and server `172.17.0.2:5432`; there were no
application tables. The acceptance run used a newly created isolated schema and
removed it in cleanup. It ran the actual full Tortoise/Aerich baseline, then Stage 4
and Stage 5 migrations, with populated upgrade/downgrade checks. PostgreSQL catalog
checks verified the four FK definitions and `NO ACTION` delete type, nullable
columns, relation loading and writes, invalid-reference rejection, the five former
composite-key tuples, and all twelve association FK/unique/NULL behaviors. Index
definitions were preserved across Stage 5 upgrade/downgrade; all indexes were valid
and ready, including the twelve Stage 4 trigram GIN indexes after upgrade. The
temporary schema was absent after cleanup and the database again had no application
tables.
