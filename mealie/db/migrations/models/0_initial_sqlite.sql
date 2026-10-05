CREATE TABLE IF NOT EXISTS "groups" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL UNIQUE,
    "slug" TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS "idx_groups_created_808c09" ON "groups" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_groups_name_bf0e14" ON "groups" ("name");
CREATE INDEX IF NOT EXISTS "idx_groups_slug_487dcd" ON "groups" ("slug");
CREATE TABLE IF NOT EXISTS "ai_provider_settings" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "default_provider_id" CHAR(36),
    "audio_provider_id" CHAR(36),
    "image_provider_id" CHAR(36),
    "group_id" CHAR(36) NOT NULL UNIQUE REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_ai_provider_group_i_62b043" UNIQUE ("group_id")
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_6d6798" ON "ai_provider_settings" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_default_ac9da3" ON "ai_provider_settings" ("default_provider_id");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_audio_p_4c7df9" ON "ai_provider_settings" ("audio_provider_id");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_image_p_5ddff1" ON "ai_provider_settings" ("image_provider_id");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_group_i_62b043" ON "ai_provider_settings" ("group_id");
CREATE TABLE IF NOT EXISTS "ai_providers" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "base_url" TEXT,
    "api_key" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "timeout" INT NOT NULL DEFAULT 300,
    "settings_id" CHAR(36) NOT NULL REFERENCES "ai_provider_settings" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_ai_provider_name_1ed64d" UNIQUE ("name", "settings_id")
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_5a73da" ON "ai_providers" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_name_16f2b9" ON "ai_providers" ("name");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_setting_423219" ON "ai_providers" ("settings_id");
CREATE TABLE IF NOT EXISTS "ai_provider_headers" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "key_name" TEXT,
    "value" TEXT,
    "provider_id" CHAR(36) NOT NULL REFERENCES "ai_providers" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_7902f5" ON "ai_provider_headers" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_provide_8ce377" ON "ai_provider_headers" ("provider_id");
CREATE TABLE IF NOT EXISTS "ai_provider_params" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "key_name" TEXT,
    "value" TEXT,
    "provider_id" CHAR(36) NOT NULL REFERENCES "ai_providers" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_ai_provider_created_c7c70d" ON "ai_provider_params" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ai_provider_provide_a482c5" ON "ai_provider_params" ("provider_id");
CREATE TABLE IF NOT EXISTS "categories" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_categories_slug_eae0ed" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_categories_created_814054" ON "categories" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_categories_name_c47ef4" ON "categories" ("name");
CREATE INDEX IF NOT EXISTS "idx_categories_slug_3a37a8" ON "categories" ("slug");
CREATE INDEX IF NOT EXISTS "idx_categories_group_i_33feca" ON "categories" ("group_id");
CREATE TABLE IF NOT EXISTS "group_data_exports" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "size" TEXT NOT NULL,
    "expires" TEXT NOT NULL,
    "group_id" CHAR(36) REFERENCES "groups" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_data__created_c36236" ON "group_data_exports" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_data__group_i_340846" ON "group_data_exports" ("group_id");
CREATE TABLE IF NOT EXISTS "group_preferences" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "private_group" INT DEFAULT 1,
    "show_announcements" INT NOT NULL DEFAULT 1,
    "first_day_of_week" INT DEFAULT 0,
    "recipe_public" INT DEFAULT 1,
    "recipe_show_nutrition" INT DEFAULT 0,
    "recipe_show_assets" INT DEFAULT 0,
    "recipe_landscape_view" INT DEFAULT 0,
    "recipe_disable_comments" INT DEFAULT 0,
    "recipe_disable_amount" INT DEFAULT 1,
    "group_id" CHAR(36) NOT NULL UNIQUE REFERENCES "groups" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_prefe_created_e9355a" ON "group_preferences" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_prefe_group_i_f8fc83" ON "group_preferences" ("group_id");
CREATE TABLE IF NOT EXISTS "households" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "slug" TEXT,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_households_group_i_884380" UNIQUE ("group_id", "name"),
    CONSTRAINT "uid_households_group_i_e33a58" UNIQUE ("group_id", "slug")
);
CREATE INDEX IF NOT EXISTS "idx_households_created_806c19" ON "households" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_households_name_d7e01d" ON "households" ("name");
CREATE INDEX IF NOT EXISTS "idx_households_slug_02d361" ON "households" ("slug");
CREATE INDEX IF NOT EXISTS "idx_households_group_i_4a6ec7" ON "households" ("group_id");
CREATE TABLE IF NOT EXISTS "cookbooks" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "position" INT NOT NULL DEFAULT 1,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "description" TEXT,
    "public" INT DEFAULT 0,
    "query_filter_string" TEXT NOT NULL,
    "require_all_categories" INT DEFAULT 1,
    "require_all_tags" INT DEFAULT 1,
    "require_all_tools" INT DEFAULT 1,
    "group_id" CHAR(36) REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cookbooks_slug_b1a1d2" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_cookbooks_created_fbeea5" ON "cookbooks" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_cookbooks_slug_aef6da" ON "cookbooks" ("slug");
CREATE INDEX IF NOT EXISTS "idx_cookbooks_group_i_34e828" ON "cookbooks" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_cookbooks_househo_3259c8" ON "cookbooks" ("household_id");
CREATE TABLE IF NOT EXISTS "group_events_notifiers" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "enabled" INT NOT NULL DEFAULT 1,
    "apprise_url" TEXT NOT NULL,
    "group_id" CHAR(36) REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_event_created_618532" ON "group_events_notifiers" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_event_group_i_33c645" ON "group_events_notifiers" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_group_event_househo_a1b531" ON "group_events_notifiers" ("household_id");
CREATE TABLE IF NOT EXISTS "group_events_notifier_options" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recipe_created" INT NOT NULL DEFAULT 0,
    "recipe_updated" INT NOT NULL DEFAULT 0,
    "recipe_deleted" INT NOT NULL DEFAULT 0,
    "user_signup" INT NOT NULL DEFAULT 0,
    "data_migrations" INT NOT NULL DEFAULT 0,
    "data_export" INT NOT NULL DEFAULT 0,
    "data_import" INT NOT NULL DEFAULT 0,
    "mealplan_entry_created" INT NOT NULL DEFAULT 0,
    "mealplan_entry_updated" INT NOT NULL DEFAULT 0,
    "mealplan_entry_deleted" INT NOT NULL DEFAULT 0,
    "shopping_list_created" INT NOT NULL DEFAULT 0,
    "shopping_list_updated" INT NOT NULL DEFAULT 0,
    "shopping_list_deleted" INT NOT NULL DEFAULT 0,
    "cookbook_created" INT NOT NULL DEFAULT 0,
    "cookbook_updated" INT NOT NULL DEFAULT 0,
    "cookbook_deleted" INT NOT NULL DEFAULT 0,
    "tag_created" INT NOT NULL DEFAULT 0,
    "tag_updated" INT NOT NULL DEFAULT 0,
    "tag_deleted" INT NOT NULL DEFAULT 0,
    "category_created" INT NOT NULL DEFAULT 0,
    "category_updated" INT NOT NULL DEFAULT 0,
    "category_deleted" INT NOT NULL DEFAULT 0,
    "label_created" INT NOT NULL DEFAULT 0,
    "label_updated" INT NOT NULL DEFAULT 0,
    "label_deleted" INT NOT NULL DEFAULT 0,
    "event_notifier_id" CHAR(36) NOT NULL UNIQUE REFERENCES "group_events_notifiers" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_event_created_5b6a43" ON "group_events_notifier_options" ("created_at");
CREATE TABLE IF NOT EXISTS "invite_tokens" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "token" TEXT NOT NULL UNIQUE,
    "uses_left" INT NOT NULL DEFAULT 1,
    "group_id" CHAR(36) REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_invite_toke_created_25e0e8" ON "invite_tokens" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_invite_toke_token_c33855" ON "invite_tokens" ("token");
CREATE INDEX IF NOT EXISTS "idx_invite_toke_group_i_afd061" ON "invite_tokens" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_invite_toke_househo_24b6b8" ON "invite_tokens" ("household_id");
CREATE TABLE IF NOT EXISTS "group_meal_plan_rules" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "day" TEXT NOT NULL,
    "entry_type" TEXT NOT NULL,
    "query_filter_string" TEXT NOT NULL,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_meal__created_2ce4b6" ON "group_meal_plan_rules" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_meal__group_i_66968d" ON "group_meal_plan_rules" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_group_meal__househo_ec8fd6" ON "group_meal_plan_rules" ("household_id");
CREATE TABLE IF NOT EXISTS "recipe_actions" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "action_type" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_created_a30601" ON "recipe_actions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_action__e6a61a" ON "recipe_actions" ("action_type");
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_title_e3c933" ON "recipe_actions" ("title");
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_group_i_e3f9b9" ON "recipe_actions" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_recipe_acti_househo_a88db4" ON "recipe_actions" ("household_id");
CREATE TABLE IF NOT EXISTS "webhook_urls" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "enabled" INT DEFAULT 0,
    "name" TEXT,
    "url" TEXT,
    "webhook_type" TEXT,
    "scheduled_time" TIME,
    "time" TEXT,
    "group_id" CHAR(36) REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_webhook_url_created_c89bf6" ON "webhook_urls" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_webhook_url_group_i_0cd33e" ON "webhook_urls" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_webhook_url_househo_09ff5a" ON "webhook_urls" ("household_id");
CREATE TABLE IF NOT EXISTS "household_preferences" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "private_household" INT DEFAULT 1,
    "show_announcements" INT NOT NULL DEFAULT 1,
    "lock_recipe_edits_from_other_households" INT DEFAULT 1,
    "first_day_of_week" INT DEFAULT 0,
    "recipe_public" INT DEFAULT 1,
    "recipe_show_nutrition" INT DEFAULT 0,
    "recipe_show_assets" INT DEFAULT 0,
    "recipe_landscape_view" INT DEFAULT 0,
    "recipe_disable_comments" INT DEFAULT 0,
    "recipe_disable_amount" INT DEFAULT 1,
    "household_id" CHAR(36) NOT NULL UNIQUE REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_household_p_created_6f7e57" ON "household_preferences" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_household_p_househo_95fa55" ON "household_preferences" ("household_id");
CREATE TABLE IF NOT EXISTS "ingredient_units" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT,
    "plural_name" TEXT,
    "description" TEXT,
    "abbreviation" TEXT,
    "plural_abbreviation" TEXT,
    "use_abbreviation" INT DEFAULT 0,
    "fraction" INT DEFAULT 1,
    "standard_quantity" REAL,
    "standard_unit" TEXT,
    "name_normalized" VARCHAR(255),
    "plural_name_normalized" VARCHAR(255),
    "abbreviation_normalized" VARCHAR(255),
    "plural_abbreviation_normalized" VARCHAR(255),
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_ingredient__name_1f2ede" UNIQUE ("name", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_5ef7e5" ON "ingredient_units" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_16dd1a" ON "ingredient_units" ("name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__plural__bccf5c" ON "ingredient_units" ("plural_name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__abbrevi_b786ec" ON "ingredient_units" ("abbreviation_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__plural__d1da63" ON "ingredient_units" ("plural_abbreviation_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__group_i_e7b652" ON "ingredient_units" ("group_id");
CREATE TABLE IF NOT EXISTS "ingredient_units_aliases" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "name_normalized" VARCHAR(255),
    "unit_id" CHAR(36) NOT NULL REFERENCES "ingredient_units" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_375636" ON "ingredient_units_aliases" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_7edb79" ON "ingredient_units_aliases" ("name_normalized");
CREATE TABLE IF NOT EXISTS "multi_purpose_labels" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(255) NOT NULL,
    "color" VARCHAR(10) NOT NULL DEFAULT '',
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_multi_purpo_name_3c6e00" UNIQUE ("name", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_multi_purpo_created_381924" ON "multi_purpose_labels" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_multi_purpo_group_i_b349e4" ON "multi_purpose_labels" ("group_id");
CREATE TABLE IF NOT EXISTS "ingredient_foods" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT,
    "plural_name" TEXT,
    "description" TEXT,
    "name_normalized" VARCHAR(255),
    "plural_name_normalized" VARCHAR(255),
    "on_hand" INT NOT NULL DEFAULT 0,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "label_id" CHAR(36) REFERENCES "multi_purpose_labels" ("id") ON DELETE SET NULL,
    CONSTRAINT "uid_ingredient__name_4fa50d" UNIQUE ("name", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_f4b9f7" ON "ingredient_foods" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_31a4cb" ON "ingredient_foods" ("name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__plural__0c2d34" ON "ingredient_foods" ("plural_name_normalized");
CREATE INDEX IF NOT EXISTS "idx_ingredient__group_i_7790f4" ON "ingredient_foods" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_ingredient__label_i_1bfec9" ON "ingredient_foods" ("label_id");
CREATE TABLE IF NOT EXISTS "ingredient_foods_aliases" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "name_normalized" VARCHAR(255),
    "food_id" CHAR(36) NOT NULL REFERENCES "ingredient_foods" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_8030b1" ON "ingredient_foods_aliases" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__name_no_40d428" ON "ingredient_foods_aliases" ("name_normalized");
CREATE TABLE IF NOT EXISTS "ingredient_food_extras" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "key_name" TEXT,
    "value" TEXT,
    "ingredient_food_id" CHAR(36) REFERENCES "ingredient_foods" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_1b8d14" ON "ingredient_food_extras" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__ingredi_82a007" ON "ingredient_food_extras" ("ingredient_food_id");
CREATE TABLE IF NOT EXISTS "ingredient_foods_substitutions" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "note" TEXT,
    "position" INT,
    "food_id" CHAR(36) NOT NULL REFERENCES "ingredient_foods" ("id") ON DELETE CASCADE,
    "substitute_food_id" CHAR(36) REFERENCES "ingredient_foods" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_ingredient__food_id_7449e7" UNIQUE ("food_id", "substitute_food_id"),
    CONSTRAINT "ingredient_foods_substitutions_no_self_substitution" CHECK ("food_id" <> "substitute_food_id"),
    CONSTRAINT "ingredient_foods_substitutions_food_or_note" CHECK ("substitute_food_id" IS NOT NULL OR "note" IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS "idx_ingredient__created_75db52" ON "ingredient_foods_substitutions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_ingredient__positio_7c83c2" ON "ingredient_foods_substitutions" ("position");
CREATE INDEX IF NOT EXISTS "idx_ingredient__food_id_0eca81" ON "ingredient_foods_substitutions" ("food_id");
CREATE INDEX IF NOT EXISTS "idx_ingredient__substit_fd6562" ON "ingredient_foods_substitutions" ("substitute_food_id");
CREATE TABLE IF NOT EXISTS "group_reports" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "timestamp" TIMESTAMP NOT NULL,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_repor_created_8c6a9f" ON "group_reports" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_repor_categor_7bfe33" ON "group_reports" ("category");
CREATE INDEX IF NOT EXISTS "idx_group_repor_group_i_0c95d4" ON "group_reports" ("group_id");
CREATE TABLE IF NOT EXISTS "report_entries" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "success" INT DEFAULT 0,
    "message" TEXT,
    "exception" TEXT,
    "timestamp" TIMESTAMP NOT NULL,
    "report_id" CHAR(36) NOT NULL REFERENCES "group_reports" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_report_entr_created_7ae1e1" ON "report_entries" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_report_entr_report__e2bd28" ON "report_entries" ("report_id");
CREATE TABLE IF NOT EXISTS "server_tasks" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "completed_date" TIMESTAMP,
    "status" TEXT NOT NULL,
    "log" TEXT,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_server_task_created_a1b77e" ON "server_tasks" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_server_task_group_i_e6487d" ON "server_tasks" ("group_id");
CREATE TABLE IF NOT EXISTS "tags" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_tags_slug_d0a4bb" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_tags_created_30658f" ON "tags" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_tags_name_15558f" ON "tags" ("name");
CREATE INDEX IF NOT EXISTS "idx_tags_slug_7bf50d" ON "tags" ("slug");
CREATE INDEX IF NOT EXISTS "idx_tags_group_i_825e74" ON "tags" ("group_id");
CREATE TABLE IF NOT EXISTS "tools" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "on_hand" INT DEFAULT 0,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_tools_slug_777dd4" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_tools_created_133d48" ON "tools" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_tools_name_a4fc51" ON "tools" ("name");
CREATE INDEX IF NOT EXISTS "idx_tools_slug_b88371" ON "tools" ("slug");
CREATE INDEX IF NOT EXISTS "idx_tools_group_i_d114fb" ON "tools" ("group_id");
CREATE TABLE IF NOT EXISTS "users" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "full_name" TEXT,
    "username" TEXT UNIQUE,
    "email" TEXT UNIQUE,
    "password" TEXT,
    "auth_method" VARCHAR(6) NOT NULL DEFAULT 'Mealie' /* MEALIE: Mealie\nLDAP: LDAP\nOIDC: OIDC */,
    "admin" INT DEFAULT 0,
    "advanced" INT DEFAULT 0,
    "cache_key" TEXT,
    "external_avatar_hash" TEXT,
    "login_attemps" INT DEFAULT 0,
    "locked_at" TIMESTAMP,
    "tokens_valid_after" TIMESTAMP,
    "show_announcements" INT NOT NULL DEFAULT 1,
    "last_read_announcement" TEXT,
    "can_manage_household" INT DEFAULT 0,
    "can_manage" INT DEFAULT 0,
    "can_invite" INT DEFAULT 0,
    "can_organize" INT DEFAULT 0,
    "owned_recipes_id" CHAR(36),
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) REFERENCES "households" ("id") ON DELETE SET NULL,
    CONSTRAINT "users_auth_method_valid" CHECK ("auth_method" IN ('Mealie', 'LDAP', 'OIDC'))
);
CREATE INDEX IF NOT EXISTS "idx_users_created_43d91f" ON "users" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_users_full_na_7cbdf3" ON "users" ("full_name");
CREATE INDEX IF NOT EXISTS "idx_users_usernam_266d85" ON "users" ("username");
CREATE INDEX IF NOT EXISTS "idx_users_email_133a6f" ON "users" ("email");
CREATE INDEX IF NOT EXISTS "idx_users_group_i_1093b8" ON "users" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_users_househo_b7dc5c" ON "users" ("household_id");
CREATE TABLE IF NOT EXISTS "long_live_tokens" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "user_id" CHAR(36) REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_long_live_t_created_c55b17" ON "long_live_tokens" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_long_live_t_token_b2e49a" ON "long_live_tokens" ("token");
CREATE INDEX IF NOT EXISTS "idx_long_live_t_user_id_bfe86f" ON "long_live_tokens" ("user_id");
CREATE TABLE IF NOT EXISTS "password_reset_tokens" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "token" VARCHAR(64) NOT NULL UNIQUE,
    "user_id" CHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_password_re_created_bab326" ON "password_reset_tokens" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_password_re_user_id_4c2a01" ON "password_reset_tokens" ("user_id");
CREATE TABLE IF NOT EXISTS "recipes" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "slug" TEXT,
    "rating" REAL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "image" TEXT,
    "total_time" TEXT,
    "prep_time" TEXT,
    "perform_time" TEXT,
    "total_time_seconds" INT,
    "prep_time_seconds" INT,
    "perform_time_seconds" INT,
    "recipe_yield" TEXT,
    "recipe_yield_quantity" REAL NOT NULL DEFAULT 0,
    "recipe_servings" REAL NOT NULL DEFAULT 0,
    "org_url" TEXT,
    "date_added" DATE,
    "date_updated" TIMESTAMP,
    "last_made" TIMESTAMP,
    "name_normalized" VARCHAR(255) NOT NULL,
    "description_normalized" VARCHAR(255),
    "cook_time" TEXT,
    "recipeCuisine" TEXT,
    "is_ocr_recipe" INT DEFAULT 0,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "user_id" CHAR(36) REFERENCES "users" ("id") ON DELETE SET NULL,
    CONSTRAINT "uid_recipes_slug_2229c3" UNIQUE ("slug", "group_id")
);
CREATE INDEX IF NOT EXISTS "idx_recipes_created_1fecae" ON "recipes" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipes_slug_1692ab" ON "recipes" ("slug");
CREATE INDEX IF NOT EXISTS "idx_recipes_rating_69c36a" ON "recipes" ("rating");
CREATE INDEX IF NOT EXISTS "idx_recipes_recipe__7a5557" ON "recipes" ("recipe_yield_quantity");
CREATE INDEX IF NOT EXISTS "idx_recipes_recipe__e8c45d" ON "recipes" ("recipe_servings");
CREATE INDEX IF NOT EXISTS "idx_recipes_name_no_a64100" ON "recipes" ("name_normalized");
CREATE INDEX IF NOT EXISTS "idx_recipes_descrip_ebb894" ON "recipes" ("description_normalized");
CREATE INDEX IF NOT EXISTS "idx_recipes_group_i_773c22" ON "recipes" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_recipes_user_id_fcb955" ON "recipes" ("user_id");
CREATE TABLE IF NOT EXISTS "api_extras" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "key_name" TEXT,
    "value" TEXT,
    "recipee_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_api_extras_created_fa2e98" ON "api_extras" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_api_extras_recipee_028dda" ON "api_extras" ("recipee_id");
CREATE TABLE IF NOT EXISTS "group_meal_plans" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date" DATE NOT NULL,
    "entry_type" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "group_id" CHAR(36) REFERENCES "groups" ("id") ON DELETE CASCADE,
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "user_id" CHAR(36) REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_group_meal__created_906ada" ON "group_meal_plans" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_group_meal__date_2ec64e" ON "group_meal_plans" ("date");
CREATE INDEX IF NOT EXISTS "idx_group_meal__entry_t_c2f873" ON "group_meal_plans" ("entry_type");
CREATE INDEX IF NOT EXISTS "idx_group_meal__title_b5bccf" ON "group_meal_plans" ("title");
CREATE INDEX IF NOT EXISTS "idx_group_meal__group_i_9d38d4" ON "group_meal_plans" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_group_meal__recipe__e0bca6" ON "group_meal_plans" ("recipe_id");
CREATE INDEX IF NOT EXISTS "idx_group_meal__user_id_7cdf68" ON "group_meal_plans" ("user_id");
CREATE TABLE IF NOT EXISTS "households_to_recipes" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_made" TIMESTAMP,
    "household_id" CHAR(36) NOT NULL REFERENCES "households" ("id") ON DELETE CASCADE,
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_households__househo_20ff1c" UNIQUE ("household_id", "recipe_id")
);
CREATE INDEX IF NOT EXISTS "idx_households__created_17ba7b" ON "households_to_recipes" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_households__househo_df6c21" ON "households_to_recipes" ("household_id");
CREATE INDEX IF NOT EXISTS "idx_households__recipe__77aaf7" ON "households_to_recipes" ("recipe_id");
CREATE TABLE IF NOT EXISTS "notes" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "title" TEXT,
    "text" TEXT,
    "reference_id" CHAR(36),
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_notes_created_04f8cc" ON "notes" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_notes_referen_64e210" ON "notes" ("reference_id");
CREATE INDEX IF NOT EXISTS "idx_notes_recipe__ae3ef8" ON "notes" ("recipe_id");
CREATE TABLE IF NOT EXISTS "recipe_nutrition" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "calories" TEXT,
    "carbohydrate_content" TEXT,
    "cholesterol_content" TEXT,
    "fat_content" TEXT,
    "fiber_content" TEXT,
    "protein_content" TEXT,
    "saturated_fat_content" TEXT,
    "sodium_content" TEXT,
    "sugar_content" TEXT,
    "trans_fat_content" TEXT,
    "unsaturated_fat_content" TEXT,
    "recipe_id" CHAR(36) NOT NULL UNIQUE REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_nutr_created_0d6956" ON "recipe_nutrition" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_nutr_recipe__704ddd" ON "recipe_nutrition" ("recipe_id");
CREATE TABLE IF NOT EXISTS "recipe_assets" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT,
    "icon" TEXT,
    "file_name" TEXT,
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_asse_created_ee685c" ON "recipe_assets" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_asse_recipe__949175" ON "recipe_assets" ("recipe_id");
CREATE TABLE IF NOT EXISTS "recipe_comments" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "text" TEXT,
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "user_id" CHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_comm_created_712053" ON "recipe_comments" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_comm_recipe__5b7873" ON "recipe_comments" ("recipe_id");
CREATE INDEX IF NOT EXISTS "idx_recipe_comm_user_id_8b552f" ON "recipe_comments" ("user_id");
CREATE TABLE IF NOT EXISTS "recipes_ingredients" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "position" INT,
    "title" TEXT,
    "note" TEXT,
    "quantity" REAL,
    "original_text" TEXT,
    "reference_id" CHAR(36),
    "note_normalized" VARCHAR(255),
    "original_text_normalized" VARCHAR(255),
    "food_id" CHAR(36) REFERENCES "ingredient_foods" ("id") ON DELETE SET NULL,
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "referenced_recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE SET NULL,
    "unit_id" CHAR(36) REFERENCES "ingredient_units" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_created_feda19" ON "recipes_ingredients" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_positio_8caf2b" ON "recipes_ingredients" ("position");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_note_no_637000" ON "recipes_ingredients" ("note_normalized");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_origina_ae326f" ON "recipes_ingredients" ("original_text_normalized");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_food_id_fea664" ON "recipes_ingredients" ("food_id");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_referen_195e11" ON "recipes_ingredients" ("referenced_recipe_id");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_unit_id_752aba" ON "recipes_ingredients" ("unit_id");
CREATE TABLE IF NOT EXISTS "recipes_ingredients_substitutions" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "note" TEXT,
    "position" INT,
    "ingredient_id" INT NOT NULL REFERENCES "recipes_ingredients" ("id") ON DELETE CASCADE,
    "substitute_food_id" CHAR(36) REFERENCES "ingredient_foods" ("id") ON DELETE CASCADE,
    CONSTRAINT "recipes_ingredients_substitutions_food_or_note" CHECK ("substitute_food_id" IS NOT NULL OR "note" IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_created_cd409c" ON "recipes_ingredients_substitutions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_positio_202397" ON "recipes_ingredients_substitutions" ("position");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_ingredi_3b06ac" ON "recipes_ingredients_substitutions" ("ingredient_id");
CREATE INDEX IF NOT EXISTS "idx_recipes_ing_substit_b7d8b7" ON "recipes_ingredients_substitutions" ("substitute_food_id");
CREATE TABLE IF NOT EXISTS "recipe_instructions" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "position" INT,
    "type" TEXT,
    "title" TEXT,
    "text" TEXT,
    "summary" TEXT,
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_inst_created_56e389" ON "recipe_instructions" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_inst_positio_dc7f47" ON "recipe_instructions" ("position");
CREATE INDEX IF NOT EXISTS "idx_recipe_inst_recipe__2db97b" ON "recipe_instructions" ("recipe_id");
CREATE TABLE IF NOT EXISTS "recipe_ingredient_ref_link" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reference_id" CHAR(36),
    "instruction_id" CHAR(36) REFERENCES "recipe_instructions" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_ingr_created_166d93" ON "recipe_ingredient_ref_link" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_ingr_referen_91056e" ON "recipe_ingredient_ref_link" ("reference_id");
CREATE INDEX IF NOT EXISTS "idx_recipe_ingr_instruc_1a2658" ON "recipe_ingredient_ref_link" ("instruction_id");
CREATE TABLE IF NOT EXISTS "recipe_note_ref_link" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reference_id" CHAR(36),
    "instruction_id" CHAR(36) REFERENCES "recipe_instructions" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_note_created_df7ab6" ON "recipe_note_ref_link" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_note_referen_560c0f" ON "recipe_note_ref_link" ("reference_id");
CREATE INDEX IF NOT EXISTS "idx_recipe_note_instruc_02680e" ON "recipe_note_ref_link" ("instruction_id");
CREATE TABLE IF NOT EXISTS "recipe_settings" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "public" INT DEFAULT 1,
    "show_nutrition" INT DEFAULT 1,
    "show_assets" INT DEFAULT 1,
    "landscape_view" INT DEFAULT 1,
    "disable_comments" INT DEFAULT 0,
    "locked" INT DEFAULT 0,
    "disable_amount" INT DEFAULT 1,
    "recipe_id" CHAR(36) NOT NULL UNIQUE REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_sett_created_67ab26" ON "recipe_settings" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_sett_recipe__9a55e8" ON "recipe_settings" ("recipe_id");
CREATE TABLE IF NOT EXISTS "recipe_share_tokens" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMP NOT NULL,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_shar_created_90d0f0" ON "recipe_share_tokens" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_shar_group_i_b0e984" ON "recipe_share_tokens" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_recipe_shar_recipe__99bea6" ON "recipe_share_tokens" ("recipe_id");
CREATE TABLE IF NOT EXISTS "recipe_timeline_events" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "subject" TEXT NOT NULL,
    "message" TEXT,
    "event_type" TEXT,
    "image" TEXT,
    "timestamp" TIMESTAMP,
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "user_id" CHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_recipe_time_created_6fccf7" ON "recipe_timeline_events" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_recipe_time_timesta_3ee621" ON "recipe_timeline_events" ("timestamp");
CREATE INDEX IF NOT EXISTS "idx_recipe_time_recipe__f203ef" ON "recipe_timeline_events" ("recipe_id");
CREATE INDEX IF NOT EXISTS "idx_recipe_time_user_id_253253" ON "recipe_timeline_events" ("user_id");
CREATE TABLE IF NOT EXISTS "shopping_lists" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT,
    "group_id" CHAR(36) NOT NULL REFERENCES "groups" ("id") ON DELETE CASCADE,
    "user_id" CHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_bee88d" ON "shopping_lists" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_group_i_7bea2d" ON "shopping_lists" ("group_id");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_user_id_ec22f0" ON "shopping_lists" ("user_id");
CREATE TABLE IF NOT EXISTS "shopping_list_extras" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "key_name" TEXT,
    "value" TEXT,
    "shopping_list_id" CHAR(36) REFERENCES "shopping_lists" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_64a046" ON "shopping_list_extras" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_shoppin_1c6cbb" ON "shopping_list_extras" ("shopping_list_id");
CREATE TABLE IF NOT EXISTS "shopping_list_items" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_ingredient" INT DEFAULT 1,
    "position" INT NOT NULL DEFAULT 0,
    "checked" INT DEFAULT 0,
    "quantity" REAL DEFAULT 1,
    "note" TEXT,
    "is_food" INT DEFAULT 0,
    "food_id" CHAR(36) REFERENCES "ingredient_foods" ("id") ON DELETE SET NULL,
    "label_id" CHAR(36) REFERENCES "multi_purpose_labels" ("id") ON DELETE SET NULL,
    "shopping_list_id" CHAR(36) REFERENCES "shopping_lists" ("id") ON DELETE CASCADE,
    "unit_id" CHAR(36) REFERENCES "ingredient_units" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_5da8b5" ON "shopping_list_items" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_positio_c4a311" ON "shopping_list_items" ("position");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_shoppin_703cbc" ON "shopping_list_items" ("shopping_list_id");
CREATE TABLE IF NOT EXISTS "shopping_list_item_extras" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "key_name" TEXT,
    "value" TEXT,
    "shopping_list_item_id" CHAR(36) REFERENCES "shopping_list_items" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_4f10bd" ON "shopping_list_item_extras" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_shoppin_1c0361" ON "shopping_list_item_extras" ("shopping_list_item_id");
CREATE TABLE IF NOT EXISTS "shopping_list_item_recipe_reference" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recipe_quantity" REAL NOT NULL,
    "recipe_scale" REAL NOT NULL DEFAULT 1,
    "recipe_note" TEXT,
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "shopping_list_item_id" CHAR(36) NOT NULL REFERENCES "shopping_list_items" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_fe1b6c" ON "shopping_list_item_recipe_reference" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_recipe__fd7f77" ON "shopping_list_item_recipe_reference" ("recipe_id");
CREATE TABLE IF NOT EXISTS "shopping_lists_multi_purpose_labels" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "position" INT NOT NULL DEFAULT 0,
    "label_id" CHAR(36) NOT NULL REFERENCES "multi_purpose_labels" ("id") ON DELETE CASCADE,
    "shopping_list_id" CHAR(36) NOT NULL REFERENCES "shopping_lists" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_shopping_li_shoppin_6bbd37" UNIQUE ("shopping_list_id", "label_id")
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_a7d8bc" ON "shopping_lists_multi_purpose_labels" ("created_at");
CREATE TABLE IF NOT EXISTS "shopping_list_recipe_reference" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recipe_quantity" REAL NOT NULL,
    "recipe_id" CHAR(36) REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "shopping_list_id" CHAR(36) NOT NULL REFERENCES "shopping_lists" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_shopping_li_created_64924c" ON "shopping_list_recipe_reference" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_shopping_li_recipe__606b5d" ON "shopping_list_recipe_reference" ("recipe_id");
CREATE TABLE IF NOT EXISTS "users_to_recipes" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "update_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "rating" REAL,
    "is_favorite" INT NOT NULL,
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "user_id" CHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_users_to_re_user_id_65bf73" UNIQUE ("user_id", "recipe_id")
);
CREATE INDEX IF NOT EXISTS "idx_users_to_re_created_352b15" ON "users_to_recipes" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_users_to_re_rating_0eae77" ON "users_to_recipes" ("rating");
CREATE INDEX IF NOT EXISTS "idx_users_to_re_is_favo_bda047" ON "users_to_recipes" ("is_favorite");
CREATE INDEX IF NOT EXISTS "idx_users_to_re_recipe__d7ebd8" ON "users_to_recipes" ("recipe_id");
CREATE INDEX IF NOT EXISTS "idx_users_to_re_user_id_1d2dbb" ON "users_to_recipes" ("user_id");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS "cookbooks_to_tags" (
    "cookbook_id" CHAR(36) NOT NULL REFERENCES "cookbooks" ("id") ON DELETE CASCADE,
    "tag_id" CHAR(36) NOT NULL REFERENCES "tags" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_cookbooks_t_cookboo_f87f89" ON "cookbooks_to_tags" ("cookbook_id", "tag_id");
CREATE TABLE IF NOT EXISTS "cookbooks_to_categories" (
    "cookbook_id" CHAR(36) NOT NULL REFERENCES "cookbooks" ("id") ON DELETE CASCADE,
    "category_id" CHAR(36) NOT NULL REFERENCES "categories" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_cookbooks_t_cookboo_560da8" ON "cookbooks_to_categories" ("cookbook_id", "category_id");
CREATE TABLE IF NOT EXISTS "cookbooks_to_tools" (
    "cookbook_id" CHAR(36) NOT NULL REFERENCES "cookbooks" ("id") ON DELETE CASCADE,
    "tool_id" CHAR(36) NOT NULL REFERENCES "tools" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_cookbooks_t_cookboo_7beac3" ON "cookbooks_to_tools" ("cookbook_id", "tool_id");
CREATE TABLE IF NOT EXISTS "plan_rules_to_households" (
    "group_plan_rule_id" CHAR(36) NOT NULL REFERENCES "group_meal_plan_rules" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) NOT NULL REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_plan_rules__group_p_84c428" ON "plan_rules_to_households" ("group_plan_rule_id", "household_id");
CREATE TABLE IF NOT EXISTS "plan_rules_to_tags" (
    "plan_rule_id" CHAR(36) NOT NULL REFERENCES "group_meal_plan_rules" ("id") ON DELETE CASCADE,
    "tag_id" CHAR(36) NOT NULL REFERENCES "tags" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_plan_rules__plan_ru_e97835" ON "plan_rules_to_tags" ("plan_rule_id", "tag_id");
CREATE TABLE IF NOT EXISTS "plan_rules_to_categories" (
    "group_plan_rule_id" CHAR(36) NOT NULL REFERENCES "group_meal_plan_rules" ("id") ON DELETE CASCADE,
    "category_id" CHAR(36) NOT NULL REFERENCES "categories" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_plan_rules__group_p_4d37e5" ON "plan_rules_to_categories" ("group_plan_rule_id", "category_id");
CREATE TABLE IF NOT EXISTS "households_to_ingredient_foods" (
    "food_id" CHAR(36) NOT NULL REFERENCES "ingredient_foods" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) NOT NULL REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_households__food_id_d0c270" ON "households_to_ingredient_foods" ("food_id", "household_id");
CREATE TABLE IF NOT EXISTS "households_to_tools" (
    "tool_id" CHAR(36) NOT NULL REFERENCES "tools" ("id") ON DELETE CASCADE,
    "household_id" CHAR(36) NOT NULL REFERENCES "households" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_households__tool_id_22793a" ON "households_to_tools" ("tool_id", "household_id");
CREATE TABLE IF NOT EXISTS "recipes_to_tags" (
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "tag_id" CHAR(36) NOT NULL REFERENCES "tags" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_recipes_to__recipe__44eeb7" ON "recipes_to_tags" ("recipe_id", "tag_id");
CREATE TABLE IF NOT EXISTS "recipes_to_categories" (
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "category_id" CHAR(36) NOT NULL REFERENCES "categories" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_recipes_to__recipe__d14e14" ON "recipes_to_categories" ("recipe_id", "category_id");
CREATE TABLE IF NOT EXISTS "recipes_to_tools" (
    "recipe_id" CHAR(36) NOT NULL REFERENCES "recipes" ("id") ON DELETE CASCADE,
    "tool_id" CHAR(36) NOT NULL REFERENCES "tools" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_recipes_to__recipe__99758a" ON "recipes_to_tools" ("recipe_id", "tool_id");
