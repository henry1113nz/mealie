from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "groups" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL UNIQUE,
    "slug" VARCHAR(255) UNIQUE
);
CREATE INDEX IF NOT EXISTS "idx_groups_created_808c09" ON "groups" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_groups_name_bf0e14" ON "groups" ("name");
CREATE INDEX IF NOT EXISTS "idx_groups_slug_487dcd" ON "groups" ("slug");
CREATE TABLE IF NOT EXISTS "ai_provider_settings" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "default_provider_id" CHAR(32),
    "audio_provider_id" CHAR(32),
    "image_provider_id" CHAR(32),
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_ai_provider_group_i_62b043" UNIQUE ("group_id")
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_6d6798" ON "ai_provider_settings" ("created_at");
CREATE TABLE IF NOT EXISTS "ai_providers" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "base_url" VARCHAR(2048),
    "api_key" TEXT NOT NULL,
    "model" VARCHAR(255) NOT NULL,
    "timeout" INT NOT NULL,
    "settings_id" CHAR(32) NOT NULL REFERENCES "ai_provider_settings" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_ai_provider_name_1ed64d" UNIQUE ("name", "settings_id")
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_5a73da" ON "ai_providers" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_name_16f2b9" ON "ai_providers" ("name");
CREATE TABLE IF NOT EXISTS "ai_provider_headers" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "key_name" VARCHAR(255),
    "value" TEXT,
    "provider_id" CHAR(32) NOT NULL REFERENCES "ai_providers" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_7902f5" ON "ai_provider_headers" ("created_at");
CREATE TABLE IF NOT EXISTS "ai_provider_params" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "key_name" VARCHAR(255),
    "value" TEXT,
    "provider_id" CHAR(32) NOT NULL REFERENCES "ai_providers" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_c7c70d" ON "ai_provider_params" ("created_at");
CREATE TABLE IF NOT EXISTS "categories" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "slug" VARCHAR(255) NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_categories_slug_eae0ed" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_categories_created_814054" ON "categories" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_categories_name_c47ef4" ON "categories" ("name");
CREATE INDEX IF NOT EXISTS "idx_categories_slug_3a37a8" ON "categories" ("slug");
CREATE TABLE IF NOT EXISTS "group_data_exports" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "size" TEXT NOT NULL,
    "expires" TIMESTAMP NOT NULL,
    "group_id" CHAR(32) REFERENCES "groups" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_data__created_c36236" ON "group_data_exports" ("created_at");
CREATE TABLE IF NOT EXISTS "group_preferences" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "private_group" INT,
    "show_announcements" INT NOT NULL,
    "first_day_of_week" INT,
    "recipe_public" INT,
    "recipe_show_nutrition" INT,
    "recipe_show_assets" INT,
    "recipe_landscape_view" INT,
    "recipe_disable_comments" INT,
    "recipe_disable_amount" INT,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_prefe_created_e9355a" ON "group_preferences" ("created_at");
CREATE TABLE IF NOT EXISTS "households" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "slug" VARCHAR(255),
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_households_group_i_884380" UNIQUE ("group_id", "name"),
    CONSTRAINT "uid_households_group_i_e33a58" UNIQUE ("group_id", "slug")
);
CREATE INDEX IF NOT EXISTS "idx_households_created_806c19" ON "households" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_households_name_d7e01d" ON "households" ("name");
CREATE INDEX IF NOT EXISTS "idx_households_slug_02d361" ON "households" ("slug");
CREATE TABLE IF NOT EXISTS "cookbooks" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "position" INT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" VARCHAR(255) NOT NULL,
    "description" TEXT,
    "public" INT,
    "query_filter_string" TEXT NOT NULL,
    "require_all_categories" INT,
    "require_all_tags" INT,
    "require_all_tools" INT,
    "group_id" CHAR(32) REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_cookbooks_slug_b1a1d2" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_cookbooks_created_fbeea5" ON "cookbooks" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_cookbooks_slug_aef6da" ON "cookbooks" ("slug");
CREATE TABLE IF NOT EXISTS "group_events_notifiers" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "enabled" INT NOT NULL,
    "apprise_url" TEXT NOT NULL,
    "group_id" CHAR(32) REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_event_created_618532" ON "group_events_notifiers" ("created_at");
CREATE TABLE IF NOT EXISTS "group_events_notifier_options" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "recipe_created" INT NOT NULL,
    "recipe_updated" INT NOT NULL,
    "recipe_deleted" INT NOT NULL,
    "user_signup" INT NOT NULL,
    "data_migrations" INT NOT NULL,
    "data_export" INT NOT NULL,
    "data_import" INT NOT NULL,
    "mealplan_entry_created" INT NOT NULL,
    "mealplan_entry_updated" INT NOT NULL,
    "mealplan_entry_deleted" INT NOT NULL,
    "shopping_list_created" INT NOT NULL,
    "shopping_list_updated" INT NOT NULL,
    "shopping_list_deleted" INT NOT NULL,
    "cookbook_created" INT NOT NULL,
    "cookbook_updated" INT NOT NULL,
    "cookbook_deleted" INT NOT NULL,
    "tag_created" INT NOT NULL,
    "tag_updated" INT NOT NULL,
    "tag_deleted" INT NOT NULL,
    "category_created" INT NOT NULL,
    "category_updated" INT NOT NULL,
    "category_deleted" INT NOT NULL,
    "label_created" INT NOT NULL,
    "label_updated" INT NOT NULL,
    "label_deleted" INT NOT NULL,
    "event_notifier_id" CHAR(32) NOT NULL REFERENCES "group_events_notifiers" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_event_created_5b6a43" ON "group_events_notifier_options" ("created_at");
CREATE TABLE IF NOT EXISTS "invite_tokens" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "token" VARCHAR(255) NOT NULL UNIQUE,
    "uses_left" INT NOT NULL,
    "group_id" CHAR(32) REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_invite_toke_created_25e0e8" ON "invite_tokens" ("created_at");
CREATE TABLE IF NOT EXISTS "group_meal_plan_rules" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "day" VARCHAR(255) NOT NULL,
    "entry_type" VARCHAR(255) NOT NULL,
    "query_filter_string" TEXT NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_meal__created_2ce4b6" ON "group_meal_plan_rules" ("created_at");
CREATE TABLE IF NOT EXISTS "recipe_actions" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "action_type" VARCHAR(255) NOT NULL,
    "title" VARCHAR(255) NOT NULL,
    "url" TEXT NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_created_a30601" ON "recipe_actions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_action__e6a61a" ON "recipe_actions" ("action_type");
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_title_e3c933" ON "recipe_actions" ("title");
CREATE TABLE IF NOT EXISTS "webhook_urls" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "enabled" INT,
    "name" TEXT,
    "url" TEXT,
    "webhook_type" TEXT,
    "scheduled_time" TIME,
    "time" TEXT,
    "group_id" CHAR(32) REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_webhook_url_created_c89bf6" ON "webhook_urls" ("created_at");
CREATE TABLE IF NOT EXISTS "household_preferences" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "private_household" INT,
    "show_announcements" INT NOT NULL,
    "lock_recipe_edits_from_other_households" INT,
    "first_day_of_week" INT,
    "recipe_public" INT,
    "recipe_show_nutrition" INT,
    "recipe_show_assets" INT,
    "recipe_landscape_view" INT,
    "recipe_disable_comments" INT,
    "recipe_disable_amount" INT,
    "household_id" CHAR(32) NOT NULL REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_household_p_created_6f7e57" ON "household_preferences" ("created_at");
CREATE TABLE IF NOT EXISTS "ingredient_units" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255),
    "plural_name" VARCHAR(255),
    "description" TEXT,
    "abbreviation" VARCHAR(255),
    "plural_abbreviation" VARCHAR(255),
    "use_abbreviation" INT,
    "fraction" INT,
    "standard_quantity" REAL,
    "standard_unit" VARCHAR(255),
    "name_normalized" VARCHAR(255),
    "plural_name_normalized" VARCHAR(255),
    "abbreviation_normalized" VARCHAR(255),
    "plural_abbreviation_normalized" VARCHAR(255),
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_5ef7e5" ON "ingredient_units" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_16dd1a" ON "ingredient_units" ("name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__plural__bccf5c" ON "ingredient_units" ("plural_name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__abbrevi_b786ec" ON "ingredient_units" ("abbreviation_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__plural__d1da63" ON "ingredient_units" ("plural_abbreviation_normalized");
CREATE TABLE IF NOT EXISTS "ingredient_units_aliases" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "name_normalized" VARCHAR(255),
    "unit_id" CHAR(32) NOT NULL REFERENCES "ingredient_units" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_ingredient__id_ff41b5" UNIQUE ("id", "unit_id")
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_375636" ON "ingredient_units_aliases" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_7edb79" ON "ingredient_units_aliases" ("name_normalized");
CREATE TABLE IF NOT EXISTS "multi_purpose_labels" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "color" VARCHAR(10) NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_multi_purpo_name_3c6e00" UNIQUE ("name", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_multi_purpo_created_381924" ON "multi_purpose_labels" ("created_at");
CREATE TABLE IF NOT EXISTS "ingredient_foods" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255),
    "plural_name" VARCHAR(255),
    "description" TEXT,
    "name_normalized" VARCHAR(255),
    "plural_name_normalized" VARCHAR(255),
    "on_hand" INT NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "label_id" CHAR(32) REFERENCES "multi_purpose_labels" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_f4b9f7" ON "ingredient_foods" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_31a4cb" ON "ingredient_foods" ("name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__plural__0c2d34" ON "ingredient_foods" ("plural_name_normalized");
CREATE TABLE IF NOT EXISTS "ingredient_foods_aliases" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "name_normalized" VARCHAR(255),
    "food_id" CHAR(32) NOT NULL REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_ingredient__id_4cbf0c" UNIQUE ("id", "food_id")
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_8030b1" ON "ingredient_foods_aliases" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_40d428" ON "ingredient_foods_aliases" ("name_normalized");
CREATE TABLE IF NOT EXISTS "ingredient_food_extras" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "key_name" VARCHAR(255),
    "value" TEXT,
    "ingredient_food_id" CHAR(32) REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_1b8d14" ON "ingredient_food_extras" ("created_at");
CREATE TABLE IF NOT EXISTS "ingredient_foods_substitutions" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "note" TEXT,
    "position" INT,
    "food_id" CHAR(32) NOT NULL REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION,
    "substitute_food_id" CHAR(32) REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_ingredient__food_id_7449e7" UNIQUE ("food_id", "substitute_food_id")
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_75db52" ON "ingredient_foods_substitutions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__positio_7c83c2" ON "ingredient_foods_substitutions" ("position");
CREATE TABLE IF NOT EXISTS "group_reports" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "category" VARCHAR(255) NOT NULL,
    "timestamp" TIMESTAMP NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_repor_created_8c6a9f" ON "group_reports" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_repor_categor_7bfe33" ON "group_reports" ("category");
CREATE TABLE IF NOT EXISTS "report_entries" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "success" INT,
    "message" TEXT,
    "exception" TEXT,
    "timestamp" TIMESTAMP NOT NULL,
    "report_id" CHAR(32) NOT NULL REFERENCES "group_reports" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_report_entr_created_7ae1e1" ON "report_entries" ("created_at");
CREATE TABLE IF NOT EXISTS "server_tasks" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" TEXT NOT NULL,
    "completed_date" TIMESTAMP,
    "status" TEXT NOT NULL,
    "log" TEXT,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_server_task_created_a1b77e" ON "server_tasks" ("created_at");
CREATE TABLE IF NOT EXISTS "tags" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "slug" VARCHAR(255) NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_tags_slug_d0a4bb" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_tags_created_30658f" ON "tags" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_tags_name_15558f" ON "tags" ("name");
CREATE INDEX IF NOT EXISTS "idx_tags_slug_7bf50d" ON "tags" ("slug");
CREATE TABLE IF NOT EXISTS "tools" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "slug" VARCHAR(255) NOT NULL,
    "on_hand" INT,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_tools_slug_777dd4" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_tools_created_133d48" ON "tools" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_tools_name_a4fc51" ON "tools" ("name");
CREATE INDEX IF NOT EXISTS "idx_tools_slug_b88371" ON "tools" ("slug");
CREATE TABLE IF NOT EXISTS "users" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "full_name" VARCHAR(255),
    "username" VARCHAR(255) UNIQUE,
    "email" VARCHAR(255) UNIQUE,
    "password" TEXT,
    "auth_method" VARCHAR(6) NOT NULL,
    "admin" INT,
    "advanced" INT,
    "cache_key" VARCHAR(255),
    "external_avatar_hash" VARCHAR(255),
    "login_attemps" INT,
    "locked_at" TIMESTAMP,
    "tokens_valid_after" TIMESTAMP,
    "show_announcements" INT NOT NULL,
    "last_read_announcement" VARCHAR(255),
    "can_manage_household" INT,
    "can_manage" INT,
    "can_invite" INT,
    "can_organize" INT,
    "owned_recipes_id" CHAR(32),
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_users_created_43d91f" ON "users" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_users_full_na_7cbdf3" ON "users" ("full_name");
CREATE INDEX IF NOT EXISTS "idx_users_usernam_266d85" ON "users" ("username");
CREATE INDEX IF NOT EXISTS "idx_users_email_133a6f" ON "users" ("email");
CREATE TABLE IF NOT EXISTS "long_live_tokens" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "token" VARCHAR(255) NOT NULL,
    "user_id" CHAR(32) REFERENCES "users" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_long_live_t_created_c55b17" ON "long_live_tokens" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_long_live_t_token_b2e49a" ON "long_live_tokens" ("token");
CREATE TABLE IF NOT EXISTS "password_reset_tokens" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "token" VARCHAR(64) NOT NULL UNIQUE,
    "user_id" CHAR(32) NOT NULL REFERENCES "users" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_password_re_created_bab326" ON "password_reset_tokens" ("created_at");
CREATE TABLE IF NOT EXISTS "recipes" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "slug" VARCHAR(255),
    "rating" REAL,
    "name" VARCHAR(255) NOT NULL,
    "description" TEXT,
    "image" VARCHAR(1024),
    "total_time" VARCHAR(255),
    "prep_time" VARCHAR(255),
    "perform_time" VARCHAR(255),
    "total_time_seconds" INT,
    "prep_time_seconds" INT,
    "perform_time_seconds" INT,
    "recipe_yield" VARCHAR(255),
    "recipe_yield_quantity" REAL NOT NULL,
    "recipe_servings" REAL NOT NULL,
    "org_url" VARCHAR(2048),
    "date_added" DATE,
    "date_updated" TIMESTAMP,
    "last_made" TIMESTAMP,
    "name_normalized" VARCHAR(255) NOT NULL,
    "description_normalized" VARCHAR(255),
    "cook_time" VARCHAR(255),
    "recipeCuisine" VARCHAR(255),
    "is_ocr_recipe" INT,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "user_id" CHAR(32) REFERENCES "users" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_recipes_slug_2229c3" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_recipes_created_1fecae" ON "recipes" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipes_slug_1692ab" ON "recipes" ("slug");
CREATE INDEX IF NOT EXISTS "idx_recipes_rating_69c36a" ON "recipes" ("rating");
CREATE INDEX IF NOT EXISTS "idx_recipes_recipe__7a5557" ON "recipes" ("recipe_yield_quantity");
CREATE INDEX IF NOT EXISTS "idx_recipes_recipe__e8c45d" ON "recipes" ("recipe_servings");
CREATE INDEX IF NOT EXISTS "idx_recipes_name_no_a64100" ON "recipes" ("name_normalized");
CREATE INDEX IF NOT EXISTS "idx_recipes_descrip_ebb894" ON "recipes" ("description_normalized");
CREATE TABLE IF NOT EXISTS "api_extras" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "key_name" VARCHAR(255),
    "value" TEXT,
    "recipee_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_api_extras_created_fa2e98" ON "api_extras" ("created_at");
CREATE TABLE IF NOT EXISTS "group_meal_plans" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "date" DATE NOT NULL,
    "entry_type" VARCHAR(255) NOT NULL,
    "title" VARCHAR(255) NOT NULL,
    "text" TEXT NOT NULL,
    "group_id" CHAR(32) REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "user_id" CHAR(32) REFERENCES "users" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_group_meal__created_906ada" ON "group_meal_plans" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_meal__date_2ec64e" ON "group_meal_plans" ("date");
CREATE INDEX IF NOT EXISTS "idx_group_meal__entry_t_c2f873" ON "group_meal_plans" ("entry_type");
CREATE INDEX IF NOT EXISTS "idx_group_meal__title_b5bccf" ON "group_meal_plans" ("title");
CREATE TABLE IF NOT EXISTS "households_to_recipes" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "last_made" TIMESTAMP,
    "household_id" CHAR(32) NOT NULL REFERENCES "households" ("id") ON DELETE NO ACTION,
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_households__househo_20ff1c" UNIQUE ("household_id", "recipe_id"),
    CONSTRAINT "uid_households__id_abdccf" UNIQUE ("id", "household_id", "recipe_id")
);
CREATE INDEX IF NOT EXISTS "idx_households__created_17ba7b" ON "households_to_recipes" ("created_at");
CREATE TABLE IF NOT EXISTS "notes" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "title" VARCHAR(255),
    "text" TEXT,
    "reference_id" CHAR(32),
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_notes_created_04f8cc" ON "notes" ("created_at");
CREATE TABLE IF NOT EXISTS "recipe_nutrition" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "calories" VARCHAR(255),
    "carbohydrate_content" VARCHAR(255),
    "cholesterol_content" VARCHAR(255),
    "fat_content" VARCHAR(255),
    "fiber_content" VARCHAR(255),
    "protein_content" VARCHAR(255),
    "saturated_fat_content" VARCHAR(255),
    "sodium_content" VARCHAR(255),
    "sugar_content" VARCHAR(255),
    "trans_fat_content" VARCHAR(255),
    "unsaturated_fat_content" VARCHAR(255),
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_nutr_created_0d6956" ON "recipe_nutrition" ("created_at");
CREATE TABLE IF NOT EXISTS "recipe_assets" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "name" VARCHAR(255),
    "icon" VARCHAR(255),
    "file_name" VARCHAR(255),
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_asse_created_ee685c" ON "recipe_assets" ("created_at");
CREATE TABLE IF NOT EXISTS "recipe_comments" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "text" TEXT,
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "user_id" CHAR(32) NOT NULL REFERENCES "users" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_comm_created_712053" ON "recipe_comments" ("created_at");
CREATE TABLE IF NOT EXISTS "recipes_ingredients" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "position" INT,
    "title" VARCHAR(255),
    "note" TEXT,
    "quantity" REAL,
    "original_text" TEXT,
    "reference_id" CHAR(32),
    "note_normalized" VARCHAR(255),
    "original_text_normalized" VARCHAR(255),
    "food_id" CHAR(32) REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION,
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "referenced_recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "unit_id" CHAR(32) REFERENCES "ingredient_units" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_created_feda19" ON "recipes_ingredients" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_positio_8caf2b" ON "recipes_ingredients" ("position");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_note_no_637000" ON "recipes_ingredients" ("note_normalized");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_origina_ae326f" ON "recipes_ingredients" ("original_text_normalized");
CREATE TABLE IF NOT EXISTS "recipes_ingredients_substitutions" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "note" TEXT,
    "position" INT,
    "ingredient_id" INT NOT NULL REFERENCES "recipes_ingredients" ("id") ON DELETE NO ACTION,
    "substitute_food_id" CHAR(32) REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_created_cd409c" ON "recipes_ingredients_substitutions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_positio_202397" ON "recipes_ingredients_substitutions" ("position");
CREATE TABLE IF NOT EXISTS "recipe_instructions" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "position" INT,
    "type" VARCHAR(255),
    "title" VARCHAR(255),
    "text" TEXT,
    "summary" TEXT,
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_inst_created_56e389" ON "recipe_instructions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_inst_positio_dc7f47" ON "recipe_instructions" ("position");
CREATE TABLE IF NOT EXISTS "recipe_ingredient_ref_link" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "reference_id" CHAR(32),
    "instruction_id" CHAR(32) REFERENCES "recipe_instructions" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_ingr_created_166d93" ON "recipe_ingredient_ref_link" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_ingr_referen_91056e" ON "recipe_ingredient_ref_link" ("reference_id");
CREATE TABLE IF NOT EXISTS "recipe_note_ref_link" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "reference_id" CHAR(32),
    "instruction_id" CHAR(32) REFERENCES "recipe_instructions" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_note_created_df7ab6" ON "recipe_note_ref_link" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_note_referen_560c0f" ON "recipe_note_ref_link" ("reference_id");
CREATE TABLE IF NOT EXISTS "recipe_settings" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "public" INT,
    "show_nutrition" INT,
    "show_assets" INT,
    "landscape_view" INT,
    "disable_comments" INT,
    "locked" INT,
    "disable_amount" INT,
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_sett_created_67ab26" ON "recipe_settings" ("created_at");
CREATE TABLE IF NOT EXISTS "recipe_share_tokens" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "expires_at" TIMESTAMP NOT NULL,
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_shar_created_90d0f0" ON "recipe_share_tokens" ("created_at");
CREATE TABLE IF NOT EXISTS "recipe_timeline_events" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "subject" VARCHAR(255) NOT NULL,
    "message" TEXT,
    "event_type" VARCHAR(255),
    "image" VARCHAR(1024),
    "timestamp" TIMESTAMP,
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "user_id" CHAR(32) NOT NULL REFERENCES "users" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_recipe_time_created_6fccf7" ON "recipe_timeline_events" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_time_timesta_3ee621" ON "recipe_timeline_events" ("timestamp");
CREATE TABLE IF NOT EXISTS "shopping_lists" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255),
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "user_id" CHAR(32) NOT NULL REFERENCES "users" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_bee88d" ON "shopping_lists" ("created_at");
CREATE TABLE IF NOT EXISTS "shopping_list_extras" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "key_name" VARCHAR(255),
    "value" TEXT,
    "shopping_list_id" CHAR(32) REFERENCES "shopping_lists" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_64a046" ON "shopping_list_extras" ("created_at");
CREATE TABLE IF NOT EXISTS "shopping_list_items" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "is_ingredient" INT,
    "position" INT NOT NULL,
    "checked" INT,
    "quantity" REAL,
    "note" TEXT,
    "is_food" INT,
    "food_id" CHAR(32) REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION,
    "label_id" CHAR(32) REFERENCES "multi_purpose_labels" ("id") ON DELETE NO ACTION,
    "shopping_list_id" CHAR(32) REFERENCES "shopping_lists" ("id") ON DELETE NO ACTION,
    "unit_id" CHAR(32) REFERENCES "ingredient_units" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_5da8b5" ON "shopping_list_items" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_positio_c4a311" ON "shopping_list_items" ("position");
CREATE TABLE IF NOT EXISTS "shopping_list_item_extras" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "key_name" VARCHAR(255),
    "value" TEXT,
    "shopping_list_item_id" CHAR(32) REFERENCES "shopping_list_items" ("id") ON DELETE NO ACTION
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_4f10bd" ON "shopping_list_item_extras" ("created_at");
CREATE TABLE IF NOT EXISTS "shopping_list_item_recipe_reference" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "recipe_quantity" REAL NOT NULL,
    "recipe_scale" REAL NOT NULL,
    "recipe_note" TEXT,
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "shopping_list_item_id" CHAR(32) NOT NULL REFERENCES "shopping_list_items" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_shopping_li_id_1f0d0e" UNIQUE ("id", "shopping_list_item_id")
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_fe1b6c" ON "shopping_list_item_recipe_reference" ("created_at");
CREATE TABLE IF NOT EXISTS "shopping_lists_multi_purpose_labels" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "position" INT NOT NULL,
    "label_id" CHAR(32) NOT NULL REFERENCES "multi_purpose_labels" ("id") ON DELETE NO ACTION,
    "shopping_list_id" CHAR(32) NOT NULL REFERENCES "shopping_lists" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_shopping_li_shoppin_6bbd37" UNIQUE ("shopping_list_id", "label_id"),
    CONSTRAINT "uid_shopping_li_id_6f2eb5" UNIQUE ("id", "shopping_list_id", "label_id")
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_a7d8bc" ON "shopping_lists_multi_purpose_labels" ("created_at");
CREATE TABLE IF NOT EXISTS "shopping_list_recipe_reference" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "recipe_quantity" REAL NOT NULL,
    "recipe_id" CHAR(32) REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "shopping_list_id" CHAR(32) NOT NULL REFERENCES "shopping_lists" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_shopping_li_id_a287cc" UNIQUE ("id", "shopping_list_id")
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_64924c" ON "shopping_list_recipe_reference" ("created_at");
CREATE TABLE IF NOT EXISTS "users_to_recipes" (
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "id" CHAR(32) NOT NULL PRIMARY KEY,
    "rating" REAL,
    "is_favorite" INT NOT NULL,
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "user_id" CHAR(32) NOT NULL REFERENCES "users" ("id") ON DELETE NO ACTION,
    CONSTRAINT "uid_users_to_re_user_id_65bf73" UNIQUE ("user_id", "recipe_id"),
    CONSTRAINT "uid_users_to_re_id_5e91bb" UNIQUE ("id", "user_id", "recipe_id")
);
CREATE INDEX IF NOT EXISTS "idx_users_to_re_created_352b15" ON "users_to_recipes" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_users_to_re_rating_0eae77" ON "users_to_recipes" ("rating");
CREATE INDEX IF NOT EXISTS "idx_users_to_re_is_favo_bda047" ON "users_to_recipes" ("is_favorite");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS "group_to_categories" (
    "group_id" CHAR(32) NOT NULL REFERENCES "groups" ("id") ON DELETE NO ACTION,
    "category_id" CHAR(32) NOT NULL REFERENCES "categories" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_group_to_ca_group_i_197f00" ON "group_to_categories" ("group_id", "category_id");
CREATE TABLE IF NOT EXISTS "households_to_ingredient_foods" (
    "household_id" CHAR(32) NOT NULL REFERENCES "households" ("id") ON DELETE NO ACTION,
    "food_id" CHAR(32) NOT NULL REFERENCES "ingredient_foods" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_households__househo_c226b5" ON "households_to_ingredient_foods" ("household_id", "food_id");
CREATE TABLE IF NOT EXISTS "households_to_tools" (
    "household_id" CHAR(32) NOT NULL REFERENCES "households" ("id") ON DELETE NO ACTION,
    "tool_id" CHAR(32) NOT NULL REFERENCES "tools" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_households__househo_1f0430" ON "households_to_tools" ("household_id", "tool_id");
CREATE TABLE IF NOT EXISTS "cookbooks_to_tags" (
    "cookbook_id" CHAR(32) NOT NULL REFERENCES "cookbooks" ("id") ON DELETE NO ACTION,
    "tag_id" CHAR(32) NOT NULL REFERENCES "tags" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_cookbooks_t_cookboo_f87f89" ON "cookbooks_to_tags" ("cookbook_id", "tag_id");
CREATE TABLE IF NOT EXISTS "cookbooks_to_tools" (
    "cookbook_id" CHAR(32) NOT NULL REFERENCES "cookbooks" ("id") ON DELETE NO ACTION,
    "tool_id" CHAR(32) NOT NULL REFERENCES "tools" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_cookbooks_t_cookboo_7beac3" ON "cookbooks_to_tools" ("cookbook_id", "tool_id");
CREATE TABLE IF NOT EXISTS "cookbooks_to_categories" (
    "cookbook_id" CHAR(32) NOT NULL REFERENCES "cookbooks" ("id") ON DELETE NO ACTION,
    "category_id" CHAR(32) NOT NULL REFERENCES "categories" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_cookbooks_t_cookboo_560da8" ON "cookbooks_to_categories" ("cookbook_id", "category_id");
CREATE TABLE IF NOT EXISTS "plan_rules_to_tags" (
    "plan_rule_id" CHAR(32) NOT NULL REFERENCES "group_meal_plan_rules" ("id") ON DELETE NO ACTION,
    "tag_id" CHAR(32) NOT NULL REFERENCES "tags" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_plan_rules__plan_ru_e97835" ON "plan_rules_to_tags" ("plan_rule_id", "tag_id");
CREATE TABLE IF NOT EXISTS "plan_rules_to_households" (
    "group_plan_rule_id" CHAR(32) NOT NULL REFERENCES "group_meal_plan_rules" ("id") ON DELETE NO ACTION,
    "household_id" CHAR(32) NOT NULL REFERENCES "households" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_plan_rules__group_p_84c428" ON "plan_rules_to_households" ("group_plan_rule_id", "household_id");
CREATE TABLE IF NOT EXISTS "plan_rules_to_categories" (
    "group_plan_rule_id" CHAR(32) NOT NULL REFERENCES "group_meal_plan_rules" ("id") ON DELETE NO ACTION,
    "category_id" CHAR(32) NOT NULL REFERENCES "categories" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_plan_rules__group_p_4d37e5" ON "plan_rules_to_categories" ("group_plan_rule_id", "category_id");
CREATE TABLE IF NOT EXISTS "recipes_to_tags" (
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "tag_id" CHAR(32) NOT NULL REFERENCES "tags" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_recipes_to__recipe__44eeb7" ON "recipes_to_tags" ("recipe_id", "tag_id");
CREATE TABLE IF NOT EXISTS "recipes_to_tools" (
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "tool_id" CHAR(32) NOT NULL REFERENCES "tools" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_recipes_to__recipe__99758a" ON "recipes_to_tools" ("recipe_id", "tool_id");
CREATE TABLE IF NOT EXISTS "recipes_to_categories" (
    "recipe_id" CHAR(32) NOT NULL REFERENCES "recipes" ("id") ON DELETE NO ACTION,
    "category_id" CHAR(32) NOT NULL REFERENCES "categories" ("id") ON DELETE NO ACTION
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_recipes_to__recipe__d14e14" ON "recipes_to_categories" ("recipe_id", "category_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "//P5tEvik="
)
