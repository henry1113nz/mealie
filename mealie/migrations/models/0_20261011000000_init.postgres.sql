CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE "server_tasks" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" TEXT NOT NULL,
    "completed_date" TIMESTAMP,
    "status" TEXT NOT NULL,
    "log" TEXT,
    "group_id" UUID NOT NULL
);
CREATE INDEX "idx_server_task_created_a1b77e" ON "server_tasks" ("created_at");
CREATE INDEX "idx_server_task_group_i_e6487d" ON "server_tasks" ("group_id");
COMMENT ON TABLE "server_tasks" IS 'Deprecated server tasks retained for database and backup compatibility.';
CREATE TABLE "long_live_tokens" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "token" VARCHAR NOT NULL,
    "user_id" UUID
);
CREATE INDEX "idx_long_live_t_created_c55b17" ON "long_live_tokens" ("created_at");
CREATE INDEX "idx_long_live_t_token_b2e49a" ON "long_live_tokens" ("token");
CREATE INDEX "idx_long_live_t_user_id_bfe86f" ON "long_live_tokens" ("user_id");
CREATE TABLE "users" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "full_name" VARCHAR,
    "username" VARCHAR UNIQUE,
    "email" VARCHAR UNIQUE,
    "password" VARCHAR,
    "auth_method" VARCHAR(6) NOT NULL,
    "admin" BOOL,
    "advanced" BOOL,
    "cache_key" VARCHAR,
    "external_avatar_hash" VARCHAR,
    "login_attemps" INT,
    "locked_at" TIMESTAMP,
    "tokens_valid_after" TIMESTAMP,
    "show_announcements" BOOL NOT NULL,
    "last_read_announcement" VARCHAR,
    "can_manage_household" BOOL,
    "can_manage" BOOL,
    "can_invite" BOOL,
    "can_organize" BOOL,
    "group_id" UUID NOT NULL,
    "household_id" UUID,
    "owned_recipes_id" UUID
);
CREATE INDEX "idx_users_created_43d91f" ON "users" ("created_at");
CREATE INDEX "idx_users_full_na_7cbdf3" ON "users" ("full_name");
CREATE INDEX "idx_users_usernam_266d85" ON "users" ("username");
CREATE INDEX "idx_users_email_133a6f" ON "users" ("email");
CREATE INDEX "idx_users_group_i_1093b8" ON "users" ("group_id");
CREATE INDEX "idx_users_househo_b7dc5c" ON "users" ("household_id");
CREATE TABLE "password_reset_tokens" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "token" VARCHAR(64) NOT NULL UNIQUE,
    "user_id" UUID NOT NULL
);
CREATE INDEX "idx_password_re_created_bab326" ON "password_reset_tokens" ("created_at");
CREATE INDEX "idx_password_re_user_id_4c2a01" ON "password_reset_tokens" ("user_id");
CREATE TABLE "users_to_recipes" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "rating" DOUBLE PRECISION,
    "is_favorite" BOOL NOT NULL,
    "recipe_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    CONSTRAINT "uid_users_to_re_user_id_65bf73" UNIQUE ("user_id", "recipe_id")
);
CREATE INDEX "idx_users_to_re_created_352b15" ON "users_to_recipes" ("created_at");
CREATE INDEX "idx_users_to_re_rating_0eae77" ON "users_to_recipes" ("rating");
CREATE INDEX "idx_users_to_re_is_favo_bda047" ON "users_to_recipes" ("is_favorite");
CREATE INDEX "idx_users_to_re_recipe__d7ebd8" ON "users_to_recipes" ("recipe_id");
CREATE INDEX "idx_users_to_re_user_id_1d2dbb" ON "users_to_recipes" ("user_id");
CREATE TABLE "groups" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL UNIQUE,
    "slug" VARCHAR UNIQUE
);
CREATE INDEX "idx_groups_created_808c09" ON "groups" ("created_at");
CREATE INDEX "idx_groups_name_bf0e14" ON "groups" ("name");
CREATE INDEX "idx_groups_slug_487dcd" ON "groups" ("slug");
CREATE TABLE "group_preferences" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "private_group" BOOL,
    "show_announcements" BOOL NOT NULL,
    "first_day_of_week" INT,
    "recipe_public" BOOL,
    "recipe_show_nutrition" BOOL,
    "recipe_show_assets" BOOL,
    "recipe_landscape_view" BOOL,
    "recipe_disable_comments" BOOL,
    "recipe_disable_amount" BOOL,
    "group_id" UUID NOT NULL
);
CREATE INDEX "idx_group_prefe_created_e9355a" ON "group_preferences" ("created_at");
CREATE INDEX "idx_group_prefe_group_i_f8fc83" ON "group_preferences" ("group_id");
CREATE TABLE "ai_providers" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "base_url" VARCHAR,
    "api_key" VARCHAR NOT NULL,
    "model" VARCHAR NOT NULL,
    "timeout" INT NOT NULL,
    "settings_id" UUID NOT NULL,
    CONSTRAINT "uid_ai_provider_name_1ed64d" UNIQUE ("name", "settings_id")
);
CREATE INDEX "idx_ai_provider_created_5a73da" ON "ai_providers" ("created_at");
CREATE INDEX "idx_ai_provider_name_16f2b9" ON "ai_providers" ("name");
CREATE INDEX "idx_ai_provider_setting_423219" ON "ai_providers" ("settings_id");
CREATE TABLE "ai_provider_headers" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "key_name" VARCHAR,
    "value" VARCHAR,
    "provider_id" UUID NOT NULL
);
CREATE INDEX "idx_ai_provider_created_7902f5" ON "ai_provider_headers" ("created_at");
CREATE INDEX "idx_ai_provider_provide_8ce377" ON "ai_provider_headers" ("provider_id");
CREATE TABLE "ai_provider_params" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "key_name" VARCHAR,
    "value" VARCHAR,
    "provider_id" UUID NOT NULL
);
CREATE INDEX "idx_ai_provider_created_c7c70d" ON "ai_provider_params" ("created_at");
CREATE INDEX "idx_ai_provider_provide_a482c5" ON "ai_provider_params" ("provider_id");
CREATE TABLE "ai_provider_settings" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "audio_provider_id" UUID,
    "default_provider_id" UUID,
    "image_provider_id" UUID,
    "group_id" UUID NOT NULL UNIQUE
);
CREATE INDEX "idx_ai_provider_created_6d6798" ON "ai_provider_settings" ("created_at");
CREATE INDEX "idx_ai_provider_audio_p_4c7df9" ON "ai_provider_settings" ("audio_provider_id");
CREATE INDEX "idx_ai_provider_default_ac9da3" ON "ai_provider_settings" ("default_provider_id");
CREATE INDEX "idx_ai_provider_image_p_5ddff1" ON "ai_provider_settings" ("image_provider_id");
CREATE INDEX "idx_ai_provider_group_i_62b043" ON "ai_provider_settings" ("group_id");
CREATE TABLE "group_data_exports" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "filename" VARCHAR NOT NULL,
    "path" VARCHAR NOT NULL,
    "size" VARCHAR NOT NULL,
    "expires" VARCHAR NOT NULL,
    "group_id" UUID
);
CREATE INDEX "idx_group_data__created_c36236" ON "group_data_exports" ("created_at");
CREATE INDEX "idx_group_data__group_i_340846" ON "group_data_exports" ("group_id");
CREATE TABLE "report_entries" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "success" BOOL,
    "message" VARCHAR,
    "exception" VARCHAR,
    "timestamp" TIMESTAMP NOT NULL,
    "report_id" UUID NOT NULL
);
CREATE INDEX "idx_report_entr_created_7ae1e1" ON "report_entries" ("created_at");
CREATE INDEX "idx_report_entr_report__e2bd28" ON "report_entries" ("report_id");
CREATE TABLE "group_reports" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "status" VARCHAR NOT NULL,
    "category" VARCHAR NOT NULL,
    "timestamp" TIMESTAMP NOT NULL,
    "group_id" UUID NOT NULL
);
CREATE INDEX "idx_group_repor_created_8c6a9f" ON "group_reports" ("created_at");
CREATE INDEX "idx_group_repor_categor_7bfe33" ON "group_reports" ("category");
CREATE INDEX "idx_group_repor_group_i_0c95d4" ON "group_reports" ("group_id");
CREATE TABLE "households" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "slug" VARCHAR,
    "group_id" UUID NOT NULL,
    CONSTRAINT "uid_households_group_i_884380" UNIQUE ("group_id", "name"),
    CONSTRAINT "uid_households_group_i_e33a58" UNIQUE ("group_id", "slug")
);
CREATE INDEX "idx_households_created_806c19" ON "households" ("created_at");
CREATE INDEX "idx_households_name_d7e01d" ON "households" ("name");
CREATE INDEX "idx_households_slug_02d361" ON "households" ("slug");
CREATE INDEX "idx_households_group_i_4a6ec7" ON "households" ("group_id");
CREATE TABLE "household_preferences" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "private_household" BOOL,
    "show_announcements" BOOL NOT NULL,
    "lock_recipe_edits_from_other_households" BOOL,
    "first_day_of_week" INT,
    "recipe_public" BOOL,
    "recipe_show_nutrition" BOOL,
    "recipe_show_assets" BOOL,
    "recipe_landscape_view" BOOL,
    "recipe_disable_comments" BOOL,
    "recipe_disable_amount" BOOL,
    "household_id" UUID NOT NULL
);
CREATE INDEX "idx_household_p_created_6f7e57" ON "household_preferences" ("created_at");
CREATE INDEX "idx_household_p_househo_95fa55" ON "household_preferences" ("household_id");
CREATE TABLE "cookbooks" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "position" INT NOT NULL,
    "name" VARCHAR NOT NULL,
    "slug" VARCHAR NOT NULL,
    "description" VARCHAR,
    "public" BOOL,
    "query_filter_string" VARCHAR NOT NULL,
    "require_all_categories" BOOL,
    "require_all_tags" BOOL,
    "require_all_tools" BOOL,
    "group_id" UUID,
    "household_id" UUID,
    CONSTRAINT "uid_cookbooks_slug_b1a1d2" UNIQUE ("slug", "group_id")
);
CREATE INDEX "idx_cookbooks_created_fbeea5" ON "cookbooks" ("created_at");
CREATE INDEX "idx_cookbooks_slug_aef6da" ON "cookbooks" ("slug");
CREATE INDEX "idx_cookbooks_group_i_34e828" ON "cookbooks" ("group_id");
CREATE INDEX "idx_cookbooks_househo_3259c8" ON "cookbooks" ("household_id");
CREATE TABLE "group_events_notifiers" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "enabled" BOOL NOT NULL,
    "apprise_url" VARCHAR NOT NULL,
    "group_id" UUID,
    "household_id" UUID
);
CREATE INDEX "idx_group_event_created_618532" ON "group_events_notifiers" ("created_at");
CREATE INDEX "idx_group_event_group_i_33c645" ON "group_events_notifiers" ("group_id");
CREATE INDEX "idx_group_event_househo_a1b531" ON "group_events_notifiers" ("household_id");
CREATE TABLE "group_events_notifier_options" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "recipe_created" BOOL NOT NULL,
    "recipe_updated" BOOL NOT NULL,
    "recipe_deleted" BOOL NOT NULL,
    "user_signup" BOOL NOT NULL,
    "data_migrations" BOOL NOT NULL,
    "data_export" BOOL NOT NULL,
    "data_import" BOOL NOT NULL,
    "mealplan_entry_created" BOOL NOT NULL,
    "mealplan_entry_updated" BOOL NOT NULL,
    "mealplan_entry_deleted" BOOL NOT NULL,
    "shopping_list_created" BOOL NOT NULL,
    "shopping_list_updated" BOOL NOT NULL,
    "shopping_list_deleted" BOOL NOT NULL,
    "cookbook_created" BOOL NOT NULL,
    "cookbook_updated" BOOL NOT NULL,
    "cookbook_deleted" BOOL NOT NULL,
    "tag_created" BOOL NOT NULL,
    "tag_updated" BOOL NOT NULL,
    "tag_deleted" BOOL NOT NULL,
    "category_created" BOOL NOT NULL,
    "category_updated" BOOL NOT NULL,
    "category_deleted" BOOL NOT NULL,
    "label_created" BOOL NOT NULL,
    "label_updated" BOOL NOT NULL,
    "label_deleted" BOOL NOT NULL,
    "event_notifier_id" UUID NOT NULL
);
CREATE INDEX "idx_group_event_created_5b6a43" ON "group_events_notifier_options" ("created_at");
CREATE TABLE "households_to_recipes" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "last_made" TIMESTAMP,
    "household_id" UUID NOT NULL,
    "recipe_id" UUID NOT NULL,
    CONSTRAINT "uid_households__househo_20ff1c" UNIQUE ("household_id", "recipe_id")
);
CREATE INDEX "idx_households__created_17ba7b" ON "households_to_recipes" ("created_at");
CREATE INDEX "idx_households__househo_df6c21" ON "households_to_recipes" ("household_id");
CREATE INDEX "idx_households__recipe__77aaf7" ON "households_to_recipes" ("recipe_id");
CREATE TABLE "invite_tokens" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "token" VARCHAR NOT NULL UNIQUE,
    "uses_left" INT NOT NULL,
    "group_id" UUID,
    "household_id" UUID
);
CREATE INDEX "idx_invite_toke_created_25e0e8" ON "invite_tokens" ("created_at");
CREATE INDEX "idx_invite_toke_token_c33855" ON "invite_tokens" ("token");
CREATE INDEX "idx_invite_toke_group_i_afd061" ON "invite_tokens" ("group_id");
CREATE INDEX "idx_invite_toke_househo_24b6b8" ON "invite_tokens" ("household_id");
CREATE TABLE "group_meal_plans" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "date" DATE NOT NULL,
    "entry_type" VARCHAR NOT NULL,
    "title" VARCHAR NOT NULL,
    "text" VARCHAR NOT NULL,
    "group_id" UUID,
    "recipe_id" UUID,
    "user_id" UUID
);
CREATE INDEX "idx_group_meal__created_906ada" ON "group_meal_plans" ("created_at");
CREATE INDEX "idx_group_meal__date_2ec64e" ON "group_meal_plans" ("date");
CREATE INDEX "idx_group_meal__entry_t_c2f873" ON "group_meal_plans" ("entry_type");
CREATE INDEX "idx_group_meal__title_b5bccf" ON "group_meal_plans" ("title");
CREATE INDEX "idx_group_meal__group_i_9d38d4" ON "group_meal_plans" ("group_id");
CREATE INDEX "idx_group_meal__recipe__e0bca6" ON "group_meal_plans" ("recipe_id");
CREATE INDEX "idx_group_meal__user_id_7cdf68" ON "group_meal_plans" ("user_id");
CREATE TABLE "group_meal_plan_rules" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "day" VARCHAR NOT NULL,
    "entry_type" VARCHAR NOT NULL,
    "query_filter_string" VARCHAR NOT NULL,
    "group_id" UUID NOT NULL,
    "household_id" UUID
);
CREATE INDEX "idx_group_meal__created_2ce4b6" ON "group_meal_plan_rules" ("created_at");
CREATE INDEX "idx_group_meal__group_i_66968d" ON "group_meal_plan_rules" ("group_id");
CREATE INDEX "idx_group_meal__househo_ec8fd6" ON "group_meal_plan_rules" ("household_id");
CREATE TABLE "recipe_actions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "action_type" VARCHAR NOT NULL,
    "title" VARCHAR NOT NULL,
    "url" VARCHAR NOT NULL,
    "group_id" UUID NOT NULL,
    "household_id" UUID
);
CREATE INDEX "idx_recipe_acti_created_a30601" ON "recipe_actions" ("created_at");
CREATE INDEX "idx_recipe_acti_action__e6a61a" ON "recipe_actions" ("action_type");
CREATE INDEX "idx_recipe_acti_title_e3c933" ON "recipe_actions" ("title");
CREATE INDEX "idx_recipe_acti_group_i_e3f9b9" ON "recipe_actions" ("group_id");
CREATE INDEX "idx_recipe_acti_househo_a88db4" ON "recipe_actions" ("household_id");
CREATE TABLE "shopping_lists" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR,
    "group_id" UUID NOT NULL,
    "user_id" UUID NOT NULL
);
CREATE INDEX "idx_shopping_li_created_bee88d" ON "shopping_lists" ("created_at");
CREATE INDEX "idx_shopping_li_group_i_7bea2d" ON "shopping_lists" ("group_id");
CREATE INDEX "idx_shopping_li_user_id_ec22f0" ON "shopping_lists" ("user_id");
CREATE TABLE "shopping_list_extras" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "key_name" VARCHAR,
    "value" VARCHAR,
    "shopping_list_id" UUID
);
CREATE INDEX "idx_shopping_li_created_64a046" ON "shopping_list_extras" ("created_at");
CREATE INDEX "idx_shopping_li_shoppin_1c6cbb" ON "shopping_list_extras" ("shopping_list_id");
CREATE TABLE "shopping_list_items" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "is_ingredient" BOOL,
    "position" INT NOT NULL,
    "checked" BOOL,
    "quantity" DOUBLE PRECISION,
    "note" VARCHAR,
    "is_food" BOOL,
    "food_id" UUID,
    "label_id" UUID,
    "shopping_list_id" UUID,
    "unit_id" UUID
);
CREATE INDEX "idx_shopping_li_created_5da8b5" ON "shopping_list_items" ("created_at");
CREATE INDEX "idx_shopping_li_positio_c4a311" ON "shopping_list_items" ("position");
CREATE INDEX "idx_shopping_li_shoppin_703cbc" ON "shopping_list_items" ("shopping_list_id");
CREATE TABLE "shopping_list_item_extras" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "key_name" VARCHAR,
    "value" VARCHAR,
    "shopping_list_item_id" UUID
);
CREATE INDEX "idx_shopping_li_created_4f10bd" ON "shopping_list_item_extras" ("created_at");
CREATE INDEX "idx_shopping_li_shoppin_1c0361" ON "shopping_list_item_extras" ("shopping_list_item_id");
CREATE TABLE "shopping_list_item_recipe_reference" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "recipe_quantity" DOUBLE PRECISION NOT NULL,
    "recipe_scale" DOUBLE PRECISION NOT NULL,
    "recipe_note" VARCHAR,
    "recipe_id" UUID,
    "shopping_list_item_id" UUID NOT NULL
);
CREATE INDEX "idx_shopping_li_created_fe1b6c" ON "shopping_list_item_recipe_reference" ("created_at");
CREATE INDEX "idx_shopping_li_recipe__fd7f77" ON "shopping_list_item_recipe_reference" ("recipe_id");
CREATE TABLE "shopping_lists_multi_purpose_labels" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "position" INT NOT NULL,
    "label_id" UUID NOT NULL,
    "shopping_list_id" UUID NOT NULL,
    CONSTRAINT "uid_shopping_li_shoppin_6bbd37" UNIQUE ("shopping_list_id", "label_id")
);
CREATE INDEX "idx_shopping_li_created_a7d8bc" ON "shopping_lists_multi_purpose_labels" ("created_at");
CREATE TABLE "shopping_list_recipe_reference" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "recipe_quantity" DOUBLE PRECISION NOT NULL,
    "recipe_id" UUID,
    "shopping_list_id" UUID NOT NULL
);
CREATE INDEX "idx_shopping_li_created_64924c" ON "shopping_list_recipe_reference" ("created_at");
CREATE INDEX "idx_shopping_li_recipe__606b5d" ON "shopping_list_recipe_reference" ("recipe_id");
CREATE TABLE "webhook_urls" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "enabled" BOOL,
    "name" VARCHAR,
    "url" VARCHAR,
    "webhook_type" VARCHAR,
    "scheduled_time" TIME,
    "time" VARCHAR,
    "group_id" UUID,
    "household_id" UUID
);
CREATE INDEX "idx_webhook_url_created_c89bf6" ON "webhook_urls" ("created_at");
CREATE INDEX "idx_webhook_url_group_i_0cd33e" ON "webhook_urls" ("group_id");
CREATE INDEX "idx_webhook_url_househo_09ff5a" ON "webhook_urls" ("household_id");
CREATE TABLE "api_extras" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "key_name" VARCHAR,
    "value" VARCHAR,
    "recipee_id" UUID
);
CREATE INDEX "idx_api_extras_created_fa2e98" ON "api_extras" ("created_at");
CREATE INDEX "idx_api_extras_recipee_028dda" ON "api_extras" ("recipee_id");
CREATE TABLE "ingredient_food_extras" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "key_name" VARCHAR,
    "value" VARCHAR,
    "ingredient_food_id" UUID
);
CREATE INDEX "idx_ingredient__created_1b8d14" ON "ingredient_food_extras" ("created_at");
CREATE INDEX "idx_ingredient__ingredi_82a007" ON "ingredient_food_extras" ("ingredient_food_id");
CREATE TABLE "recipe_assets" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR,
    "icon" VARCHAR,
    "file_name" VARCHAR,
    "recipe_id" UUID
);
CREATE INDEX "idx_recipe_asse_created_ee685c" ON "recipe_assets" ("created_at");
CREATE INDEX "idx_recipe_asse_recipe__949175" ON "recipe_assets" ("recipe_id");
CREATE TABLE "categories" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "slug" VARCHAR NOT NULL,
    "group_id" UUID NOT NULL,
    CONSTRAINT "uid_categories_slug_eae0ed" UNIQUE ("slug", "group_id")
);
CREATE INDEX "idx_categories_created_814054" ON "categories" ("created_at");
CREATE INDEX "idx_categories_name_c47ef4" ON "categories" ("name");
CREATE INDEX "idx_categories_slug_3a37a8" ON "categories" ("slug");
CREATE INDEX "idx_categories_group_i_33feca" ON "categories" ("group_id");
CREATE TABLE "recipe_comments" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "text" VARCHAR,
    "recipe_id" UUID NOT NULL,
    "user_id" UUID NOT NULL
);
CREATE INDEX "idx_recipe_comm_created_712053" ON "recipe_comments" ("created_at");
CREATE INDEX "idx_recipe_comm_recipe__5b7873" ON "recipe_comments" ("recipe_id");
CREATE INDEX "idx_recipe_comm_user_id_8b552f" ON "recipe_comments" ("user_id");
CREATE TABLE "ingredient_foods_aliases" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "name_normalized" VARCHAR,
    "food_id" UUID NOT NULL,
    CONSTRAINT "uid_ingredient__id_4cbf0c" UNIQUE ("id", "food_id")
);
CREATE INDEX "idx_ingredient__created_8030b1" ON "ingredient_foods_aliases" ("created_at");
CREATE INDEX "idx_ingredient__name_no_40d428" ON "ingredient_foods_aliases" ("name_normalized");
CREATE TABLE "ingredient_foods" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR,
    "plural_name" VARCHAR,
    "description" VARCHAR,
    "name_normalized" VARCHAR,
    "plural_name_normalized" VARCHAR,
    "on_hand" BOOL NOT NULL,
    "group_id" UUID NOT NULL,
    "label_id" UUID,
    CONSTRAINT "uid_ingredient__name_4fa50d" UNIQUE ("name", "group_id")
);
CREATE INDEX "idx_ingredient__created_f4b9f7" ON "ingredient_foods" ("created_at");
CREATE INDEX "idx_ingredient__name_no_31a4cb" ON "ingredient_foods" ("name_normalized");
CREATE INDEX "idx_ingredient__plural__0c2d34" ON "ingredient_foods" ("plural_name_normalized");
CREATE INDEX "idx_ingredient__group_i_7790f4" ON "ingredient_foods" ("group_id");
CREATE INDEX "idx_ingredient__label_i_1bfec9" ON "ingredient_foods" ("label_id");
CREATE TABLE "ingredient_foods_substitutions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "note" VARCHAR,
    "position" INT,
    "food_id" UUID NOT NULL,
    "substitute_food_id" UUID,
    CONSTRAINT "uid_ingredient__food_id_7449e7" UNIQUE ("food_id", "substitute_food_id"),
    CONSTRAINT "ingredient_foods_substitutions_no_self_substitution" CHECK ("food_id" != "substitute_food_id"),
    CONSTRAINT "ingredient_foods_substitutions_food_or_note" CHECK ("substitute_food_id" IS NOT NULL OR "note" IS NOT NULL)
);
CREATE INDEX "idx_ingredient__created_75db52" ON "ingredient_foods_substitutions" ("created_at");
CREATE INDEX "idx_ingredient__positio_7c83c2" ON "ingredient_foods_substitutions" ("position");
CREATE INDEX "idx_ingredient__food_id_0eca81" ON "ingredient_foods_substitutions" ("food_id");
CREATE INDEX "idx_ingredient__substit_fd6562" ON "ingredient_foods_substitutions" ("substitute_food_id");
CREATE TABLE "ingredient_units_aliases" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "name_normalized" VARCHAR,
    "unit_id" UUID NOT NULL,
    CONSTRAINT "uid_ingredient__id_ff41b5" UNIQUE ("id", "unit_id")
);
CREATE INDEX "idx_ingredient__created_375636" ON "ingredient_units_aliases" ("created_at");
CREATE INDEX "idx_ingredient__name_no_7edb79" ON "ingredient_units_aliases" ("name_normalized");
CREATE TABLE "ingredient_units" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR,
    "plural_name" VARCHAR,
    "description" VARCHAR,
    "abbreviation" VARCHAR,
    "plural_abbreviation" VARCHAR,
    "use_abbreviation" BOOL,
    "fraction" BOOL,
    "standard_quantity" DOUBLE PRECISION,
    "standard_unit" VARCHAR,
    "name_normalized" VARCHAR,
    "plural_name_normalized" VARCHAR,
    "abbreviation_normalized" VARCHAR,
    "plural_abbreviation_normalized" VARCHAR,
    "group_id" UUID NOT NULL,
    CONSTRAINT "uid_ingredient__name_1f2ede" UNIQUE ("name", "group_id")
);
CREATE INDEX "idx_ingredient__created_5ef7e5" ON "ingredient_units" ("created_at");
CREATE INDEX "idx_ingredient__name_no_16dd1a" ON "ingredient_units" ("name_normalized");
CREATE INDEX "idx_ingredient__plural__bccf5c" ON "ingredient_units" ("plural_name_normalized");
CREATE INDEX "idx_ingredient__abbrevi_b786ec" ON "ingredient_units" ("abbreviation_normalized");
CREATE INDEX "idx_ingredient__plural__d1da63" ON "ingredient_units" ("plural_abbreviation_normalized");
CREATE INDEX "idx_ingredient__group_i_e7b652" ON "ingredient_units" ("group_id");
CREATE TABLE "recipes_ingredients" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "position" INT,
    "title" VARCHAR,
    "note" VARCHAR,
    "quantity" DOUBLE PRECISION,
    "original_text" VARCHAR,
    "reference_id" UUID,
    "note_normalized" VARCHAR,
    "original_text_normalized" VARCHAR,
    "food_id" UUID,
    "recipe_id" UUID,
    "referenced_recipe_id" UUID,
    "unit_id" UUID
);
CREATE INDEX "idx_recipes_ing_created_feda19" ON "recipes_ingredients" ("created_at");
CREATE INDEX "idx_recipes_ing_positio_8caf2b" ON "recipes_ingredients" ("position");
CREATE INDEX "idx_recipes_ing_note_no_637000" ON "recipes_ingredients" ("note_normalized");
CREATE INDEX "idx_recipes_ing_origina_ae326f" ON "recipes_ingredients" ("original_text_normalized");
CREATE INDEX "idx_recipes_ing_food_id_fea664" ON "recipes_ingredients" ("food_id");
CREATE INDEX "idx_recipes_ing_referen_195e11" ON "recipes_ingredients" ("referenced_recipe_id");
CREATE INDEX "idx_recipes_ing_unit_id_752aba" ON "recipes_ingredients" ("unit_id");
CREATE TABLE "recipes_ingredients_substitutions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "note" VARCHAR,
    "position" INT,
    "ingredient_id" INT NOT NULL,
    "substitute_food_id" UUID,
    CONSTRAINT "recipes_ingredients_substitutions_food_or_note" CHECK ("substitute_food_id" IS NOT NULL OR "note" IS NOT NULL)
);
CREATE INDEX "idx_recipes_ing_created_cd409c" ON "recipes_ingredients_substitutions" ("created_at");
CREATE INDEX "idx_recipes_ing_positio_202397" ON "recipes_ingredients_substitutions" ("position");
CREATE INDEX "idx_recipes_ing_ingredi_3b06ac" ON "recipes_ingredients_substitutions" ("ingredient_id");
CREATE INDEX "idx_recipes_ing_substit_b7d8b7" ON "recipes_ingredients_substitutions" ("substitute_food_id");
CREATE TABLE "recipe_ingredient_ref_link" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "reference_id" UUID,
    "instruction_id" UUID
);
CREATE INDEX "idx_recipe_ingr_created_166d93" ON "recipe_ingredient_ref_link" ("created_at");
CREATE INDEX "idx_recipe_ingr_referen_91056e" ON "recipe_ingredient_ref_link" ("reference_id");
CREATE INDEX "idx_recipe_ingr_instruc_1a2658" ON "recipe_ingredient_ref_link" ("instruction_id");
CREATE TABLE "recipe_instructions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "position" INT,
    "type" VARCHAR,
    "title" VARCHAR,
    "text" VARCHAR,
    "summary" VARCHAR,
    "recipe_id" UUID
);
CREATE INDEX "idx_recipe_inst_created_56e389" ON "recipe_instructions" ("created_at");
CREATE INDEX "idx_recipe_inst_positio_dc7f47" ON "recipe_instructions" ("position");
CREATE INDEX "idx_recipe_inst_recipe__2db97b" ON "recipe_instructions" ("recipe_id");
CREATE TABLE "recipe_note_ref_link" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "reference_id" UUID,
    "instruction_id" UUID
);
CREATE INDEX "idx_recipe_note_created_df7ab6" ON "recipe_note_ref_link" ("created_at");
CREATE INDEX "idx_recipe_note_referen_560c0f" ON "recipe_note_ref_link" ("reference_id");
CREATE INDEX "idx_recipe_note_instruc_02680e" ON "recipe_note_ref_link" ("instruction_id");
CREATE TABLE "multi_purpose_labels" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR(255) NOT NULL,
    "color" VARCHAR(10) NOT NULL,
    "group_id" UUID NOT NULL,
    CONSTRAINT "uid_multi_purpo_name_3c6e00" UNIQUE ("name", "group_id")
);
CREATE INDEX "idx_multi_purpo_created_381924" ON "multi_purpose_labels" ("created_at");
CREATE INDEX "idx_multi_purpo_group_i_b349e4" ON "multi_purpose_labels" ("group_id");
CREATE TABLE "notes" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "title" VARCHAR,
    "text" VARCHAR,
    "reference_id" UUID,
    "recipe_id" UUID
);
CREATE INDEX "idx_notes_created_04f8cc" ON "notes" ("created_at");
CREATE INDEX "idx_notes_referen_64e210" ON "notes" ("reference_id");
CREATE INDEX "idx_notes_recipe__ae3ef8" ON "notes" ("recipe_id");
CREATE TABLE "recipe_nutrition" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "calories" VARCHAR,
    "carbohydrate_content" VARCHAR,
    "cholesterol_content" VARCHAR,
    "fat_content" VARCHAR,
    "fiber_content" VARCHAR,
    "protein_content" VARCHAR,
    "saturated_fat_content" VARCHAR,
    "sodium_content" VARCHAR,
    "sugar_content" VARCHAR,
    "trans_fat_content" VARCHAR,
    "unsaturated_fat_content" VARCHAR,
    "recipe_id" UUID
);
CREATE INDEX "idx_recipe_nutr_created_0d6956" ON "recipe_nutrition" ("created_at");
CREATE INDEX "idx_recipe_nutr_recipe__704ddd" ON "recipe_nutrition" ("recipe_id");
CREATE TABLE "recipes" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "slug" VARCHAR,
    "rating" DOUBLE PRECISION,
    "name" VARCHAR NOT NULL,
    "description" VARCHAR,
    "image" VARCHAR,
    "total_time" VARCHAR,
    "prep_time" VARCHAR,
    "perform_time" VARCHAR,
    "total_time_seconds" INT,
    "prep_time_seconds" INT,
    "perform_time_seconds" INT,
    "recipe_yield" VARCHAR,
    "recipe_yield_quantity" DOUBLE PRECISION NOT NULL,
    "recipe_servings" DOUBLE PRECISION NOT NULL,
    "org_url" VARCHAR,
    "date_added" DATE,
    "date_updated" TIMESTAMP,
    "last_made" TIMESTAMP,
    "name_normalized" VARCHAR NOT NULL,
    "description_normalized" VARCHAR,
    "cook_time" VARCHAR,
    "recipeCuisine" VARCHAR,
    "is_ocr_recipe" BOOL,
    "group_id" UUID NOT NULL,
    "user_id" UUID,
    CONSTRAINT "uid_recipes_slug_2229c3" UNIQUE ("slug", "group_id")
);
CREATE INDEX "idx_recipes_created_1fecae" ON "recipes" ("created_at");
CREATE INDEX "idx_recipes_slug_1692ab" ON "recipes" ("slug");
CREATE INDEX "idx_recipes_rating_69c36a" ON "recipes" ("rating");
CREATE INDEX "idx_recipes_recipe__7a5557" ON "recipes" ("recipe_yield_quantity");
CREATE INDEX "idx_recipes_recipe__e8c45d" ON "recipes" ("recipe_servings");
CREATE INDEX "idx_recipes_name_no_a64100" ON "recipes" ("name_normalized");
CREATE INDEX "idx_recipes_descrip_ebb894" ON "recipes" ("description_normalized");
CREATE INDEX "idx_recipes_group_i_773c22" ON "recipes" ("group_id");
CREATE INDEX "idx_recipes_user_id_fcb955" ON "recipes" ("user_id");
CREATE TABLE "recipe_timeline_events" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "subject" VARCHAR NOT NULL,
    "message" VARCHAR,
    "event_type" VARCHAR,
    "image" VARCHAR,
    "timestamp" TIMESTAMP,
    "recipe_id" UUID NOT NULL,
    "user_id" UUID NOT NULL
);
CREATE INDEX "idx_recipe_time_created_6fccf7" ON "recipe_timeline_events" ("created_at");
CREATE INDEX "idx_recipe_time_timesta_3ee621" ON "recipe_timeline_events" ("timestamp");
CREATE INDEX "idx_recipe_time_recipe__f203ef" ON "recipe_timeline_events" ("recipe_id");
CREATE INDEX "idx_recipe_time_user_id_253253" ON "recipe_timeline_events" ("user_id");
CREATE TABLE "recipe_settings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "public" BOOL,
    "show_nutrition" BOOL,
    "show_assets" BOOL,
    "landscape_view" BOOL,
    "disable_comments" BOOL,
    "locked" BOOL,
    "disable_amount" BOOL,
    "recipe_id" UUID
);
CREATE INDEX "idx_recipe_sett_created_67ab26" ON "recipe_settings" ("created_at");
CREATE INDEX "idx_recipe_sett_recipe__9a55e8" ON "recipe_settings" ("recipe_id");
CREATE TABLE "recipe_share_tokens" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "expires_at" TIMESTAMP NOT NULL,
    "group_id" UUID NOT NULL,
    "recipe_id" UUID NOT NULL
);
CREATE INDEX "idx_recipe_shar_created_90d0f0" ON "recipe_share_tokens" ("created_at");
CREATE INDEX "idx_recipe_shar_group_i_b0e984" ON "recipe_share_tokens" ("group_id");
CREATE INDEX "idx_recipe_shar_recipe__99bea6" ON "recipe_share_tokens" ("recipe_id");
CREATE TABLE "tags" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "slug" VARCHAR NOT NULL,
    "group_id" UUID NOT NULL,
    CONSTRAINT "uid_tags_slug_d0a4bb" UNIQUE ("slug", "group_id")
);
CREATE INDEX "idx_tags_created_30658f" ON "tags" ("created_at");
CREATE INDEX "idx_tags_name_15558f" ON "tags" ("name");
CREATE INDEX "idx_tags_slug_7bf50d" ON "tags" ("slug");
CREATE INDEX "idx_tags_group_i_825e74" ON "tags" ("group_id");
CREATE TABLE "tools" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP,
    "update_at" TIMESTAMP,
    "name" VARCHAR NOT NULL,
    "slug" VARCHAR NOT NULL,
    "on_hand" BOOL,
    "group_id" UUID NOT NULL,
    CONSTRAINT "uid_tools_slug_777dd4" UNIQUE ("slug", "group_id")
);
CREATE INDEX "idx_tools_created_133d48" ON "tools" ("created_at");
CREATE INDEX "idx_tools_name_a4fc51" ON "tools" ("name");
CREATE INDEX "idx_tools_slug_b88371" ON "tools" ("slug");
CREATE INDEX "idx_tools_group_i_d114fb" ON "tools" ("group_id");
CREATE TABLE "cookbooks_to_tags" (
    "cookbook_id" UUID REFERENCES "cookbooks" ("id") ON DELETE RESTRICT,
    "tag_id" UUID REFERENCES "tags" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_cookbooks_t_cookboo_f87f89" ON "cookbooks_to_tags" ("cookbook_id", "tag_id");
CREATE TABLE "cookbooks_to_tools" (
    "cookbook_id" UUID REFERENCES "cookbooks" ("id") ON DELETE RESTRICT,
    "tool_id" UUID REFERENCES "tools" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_cookbooks_t_cookboo_7beac3" ON "cookbooks_to_tools" ("cookbook_id", "tool_id");
CREATE TABLE "cookbooks_to_categories" (
    "cookbook_id" UUID REFERENCES "cookbooks" ("id") ON DELETE RESTRICT,
    "category_id" UUID REFERENCES "categories" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_cookbooks_t_cookboo_560da8" ON "cookbooks_to_categories" ("cookbook_id", "category_id");
CREATE INDEX "ix_cookbooks_to_categories_cookbook_id" ON "cookbooks_to_categories" ("cookbook_id");
CREATE INDEX "ix_cookbooks_to_categories_category_id" ON "cookbooks_to_categories" ("category_id");
CREATE INDEX "ix_cookbooks_to_tags_cookbook_id" ON "cookbooks_to_tags" ("cookbook_id");
CREATE INDEX "ix_cookbooks_to_tags_tag_id" ON "cookbooks_to_tags" ("tag_id");
CREATE INDEX "ix_cookbooks_to_tools_cookbook_id" ON "cookbooks_to_tools" ("cookbook_id");
CREATE INDEX "ix_cookbooks_to_tools_tool_id" ON "cookbooks_to_tools" ("tool_id");
CREATE TABLE "plan_rules_to_tags" (
    "plan_rule_id" UUID REFERENCES "group_meal_plan_rules" ("id") ON DELETE RESTRICT,
    "tag_id" UUID REFERENCES "tags" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_plan_rules__plan_ru_e97835" ON "plan_rules_to_tags" ("plan_rule_id", "tag_id");
CREATE TABLE "plan_rules_to_categories" (
    "group_plan_rule_id" UUID REFERENCES "group_meal_plan_rules" ("id") ON DELETE RESTRICT,
    "category_id" UUID REFERENCES "categories" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_plan_rules__group_p_4d37e5" ON "plan_rules_to_categories" ("group_plan_rule_id", "category_id");
CREATE TABLE "plan_rules_to_households" (
    "group_plan_rule_id" UUID REFERENCES "group_meal_plan_rules" ("id") ON DELETE RESTRICT,
    "household_id" UUID REFERENCES "households" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_plan_rules__group_p_84c428" ON "plan_rules_to_households" ("group_plan_rule_id", "household_id");
CREATE INDEX "ix_plan_rules_to_categories_group_plan_rule_id" ON "plan_rules_to_categories" ("group_plan_rule_id");
CREATE INDEX "ix_plan_rules_to_categories_category_id" ON "plan_rules_to_categories" ("category_id");
CREATE INDEX "ix_plan_rules_to_households_group_plan_rule_id" ON "plan_rules_to_households" ("group_plan_rule_id");
CREATE INDEX "ix_plan_rules_to_households_household_id" ON "plan_rules_to_households" ("household_id");
CREATE INDEX "ix_plan_rules_to_tags_plan_rule_id" ON "plan_rules_to_tags" ("plan_rule_id");
CREATE INDEX "ix_plan_rules_to_tags_tag_id" ON "plan_rules_to_tags" ("tag_id");
CREATE TABLE "group_to_categories" (
    "category_id" UUID REFERENCES "categories" ("id") ON DELETE RESTRICT,
    "group_id" UUID REFERENCES "groups" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_group_to_ca_categor_1888ce" ON "group_to_categories" ("category_id", "group_id");
CREATE INDEX "ix_group_to_categories_category_id" ON "group_to_categories" ("category_id");
CREATE INDEX "ix_group_to_categories_group_id" ON "group_to_categories" ("group_id");
CREATE TABLE "households_to_ingredient_foods" (
    "food_id" UUID REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT,
    "household_id" UUID REFERENCES "households" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_households__food_id_d0c270" ON "households_to_ingredient_foods" ("food_id", "household_id");
CREATE INDEX "ix_households_to_ingredient_foods_food_id" ON "households_to_ingredient_foods" ("food_id");
CREATE INDEX "ix_households_to_ingredient_foods_household_id" ON "households_to_ingredient_foods" ("household_id");
CREATE TABLE "recipes_to_tags" (
    "recipe_id" UUID REFERENCES "recipes" ("id") ON DELETE RESTRICT,
    "tag_id" UUID REFERENCES "tags" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_recipes_to__recipe__44eeb7" ON "recipes_to_tags" ("recipe_id", "tag_id");
CREATE TABLE "recipes_to_tools" (
    "recipe_id" UUID REFERENCES "recipes" ("id") ON DELETE RESTRICT,
    "tool_id" UUID REFERENCES "tools" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_recipes_to__recipe__99758a" ON "recipes_to_tools" ("recipe_id", "tool_id");
CREATE TABLE "recipes_to_categories" (
    "recipe_id" UUID REFERENCES "recipes" ("id") ON DELETE RESTRICT,
    "category_id" UUID REFERENCES "categories" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_recipes_to__recipe__d14e14" ON "recipes_to_categories" ("recipe_id", "category_id");
CREATE INDEX "ix_recipes_to_categories_recipe_id" ON "recipes_to_categories" ("recipe_id");
CREATE INDEX "ix_recipes_to_categories_category_id" ON "recipes_to_categories" ("category_id");
CREATE INDEX "ix_recipes_to_tags_recipe_id" ON "recipes_to_tags" ("recipe_id");
CREATE INDEX "ix_recipes_to_tags_tag_id" ON "recipes_to_tags" ("tag_id");
CREATE INDEX "ix_recipes_to_tools_recipe_id" ON "recipes_to_tools" ("recipe_id");
CREATE INDEX "ix_recipes_to_tools_tool_id" ON "recipes_to_tools" ("tool_id");
CREATE TABLE "households_to_tools" (
    "tool_id" UUID REFERENCES "tools" ("id") ON DELETE RESTRICT,
    "household_id" UUID REFERENCES "households" ("id") ON DELETE RESTRICT
);
CREATE UNIQUE INDEX "uidx_households__tool_id_22793a" ON "households_to_tools" ("tool_id", "household_id");
CREATE INDEX "ix_households_to_tools_tool_id" ON "households_to_tools" ("tool_id");
CREATE INDEX "ix_households_to_tools_household_id" ON "households_to_tools" ("household_id");
ALTER TABLE "server_tasks" ADD CONSTRAINT "fk_server_t_groups_f399f619" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "long_live_tokens" ADD CONSTRAINT "fk_long_liv_users_f6de6878" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "users" ADD CONSTRAINT "fk_users_groups_0caa2c43" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "users" ADD CONSTRAINT "fk_users_househol_05ec39d9" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "users" ADD CONSTRAINT "fk_users_recipes_c262a50b" FOREIGN KEY ("owned_recipes_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "password_reset_tokens" ADD CONSTRAINT "fk_password_users_6176974d" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "users_to_recipes" ADD CONSTRAINT "fk_users_to_recipes_c2a35c8a" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "users_to_recipes" ADD CONSTRAINT "fk_users_to_users_d0ec9014" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_preferences" ADD CONSTRAINT "fk_group_pr_groups_07dd20b7" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_providers" ADD CONSTRAINT "fk_ai_provi_ai_provi_cc87fffd" FOREIGN KEY ("settings_id") REFERENCES "ai_provider_settings" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_provider_headers" ADD CONSTRAINT "fk_ai_provi_ai_provi_4b2f48f4" FOREIGN KEY ("provider_id") REFERENCES "ai_providers" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_provider_params" ADD CONSTRAINT "fk_ai_provi_ai_provi_84611d7e" FOREIGN KEY ("provider_id") REFERENCES "ai_providers" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_provider_settings" ADD CONSTRAINT "fk_ai_provi_ai_provi_c0efbb9f" FOREIGN KEY ("audio_provider_id") REFERENCES "ai_providers" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_provider_settings" ADD CONSTRAINT "fk_ai_provi_ai_provi_a9df8257" FOREIGN KEY ("default_provider_id") REFERENCES "ai_providers" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_provider_settings" ADD CONSTRAINT "fk_ai_provi_ai_provi_77be2eff" FOREIGN KEY ("image_provider_id") REFERENCES "ai_providers" ("id") ON DELETE RESTRICT;
ALTER TABLE "ai_provider_settings" ADD CONSTRAINT "fk_ai_provi_groups_bca20b27" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_data_exports" ADD CONSTRAINT "fk_group_da_groups_971fce9d" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "report_entries" ADD CONSTRAINT "fk_report_e_group_re_ed192d31" FOREIGN KEY ("report_id") REFERENCES "group_reports" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_reports" ADD CONSTRAINT "fk_group_re_groups_2268a469" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "households" ADD CONSTRAINT "fk_househol_groups_84f1b84a" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "household_preferences" ADD CONSTRAINT "fk_househol_househol_c028ba0f" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "cookbooks" ADD CONSTRAINT "fk_cookbook_groups_fca969e0" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "cookbooks" ADD CONSTRAINT "fk_cookbook_househol_9df2e62f" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_events_notifiers" ADD CONSTRAINT "fk_group_ev_groups_61a6046d" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_events_notifiers" ADD CONSTRAINT "fk_group_ev_househol_fec3b5f5" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_events_notifier_options" ADD CONSTRAINT "fk_group_ev_group_ev_42febea8" FOREIGN KEY ("event_notifier_id") REFERENCES "group_events_notifiers" ("id") ON DELETE RESTRICT;
ALTER TABLE "households_to_recipes" ADD CONSTRAINT "fk_househol_househol_260b5475" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "households_to_recipes" ADD CONSTRAINT "fk_househol_recipes_a0f4c02c" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "invite_tokens" ADD CONSTRAINT "fk_invite_t_groups_603079c3" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "invite_tokens" ADD CONSTRAINT "fk_invite_t_househol_e3868909" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_meal_plans" ADD CONSTRAINT "fk_group_me_groups_309eee37" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_meal_plans" ADD CONSTRAINT "fk_group_me_recipes_dc3f7a55" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_meal_plans" ADD CONSTRAINT "fk_group_me_users_de9f85d0" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_meal_plan_rules" ADD CONSTRAINT "fk_group_me_groups_000449a6" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "group_meal_plan_rules" ADD CONSTRAINT "fk_group_me_househol_023a5fd4" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_actions" ADD CONSTRAINT "fk_recipe_a_groups_3908d898" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_actions" ADD CONSTRAINT "fk_recipe_a_househol_5c9a2111" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_lists" ADD CONSTRAINT "fk_shopping_groups_fe0362cf" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_lists" ADD CONSTRAINT "fk_shopping_users_822c3955" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_extras" ADD CONSTRAINT "fk_shopping_shopping_8ca56e56" FOREIGN KEY ("shopping_list_id") REFERENCES "shopping_lists" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_items" ADD CONSTRAINT "fk_shopping_ingredie_59b50808" FOREIGN KEY ("food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_items" ADD CONSTRAINT "fk_shopping_multi_pu_b4bacd41" FOREIGN KEY ("label_id") REFERENCES "multi_purpose_labels" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_items" ADD CONSTRAINT "fk_shopping_shopping_3d2b3d75" FOREIGN KEY ("shopping_list_id") REFERENCES "shopping_lists" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_items" ADD CONSTRAINT "fk_shopping_ingredie_0d6c90c8" FOREIGN KEY ("unit_id") REFERENCES "ingredient_units" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_item_extras" ADD CONSTRAINT "fk_shopping_shopping_2dbed9ba" FOREIGN KEY ("shopping_list_item_id") REFERENCES "shopping_list_items" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_item_recipe_reference" ADD CONSTRAINT "fk_shopping_recipes_e80334ce" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_item_recipe_reference" ADD CONSTRAINT "fk_shopping_shopping_45c6a343" FOREIGN KEY ("shopping_list_item_id") REFERENCES "shopping_list_items" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_lists_multi_purpose_labels" ADD CONSTRAINT "fk_shopping_multi_pu_6d0c5990" FOREIGN KEY ("label_id") REFERENCES "multi_purpose_labels" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_lists_multi_purpose_labels" ADD CONSTRAINT "fk_shopping_shopping_83b223a6" FOREIGN KEY ("shopping_list_id") REFERENCES "shopping_lists" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_recipe_reference" ADD CONSTRAINT "fk_shopping_recipes_90f821a0" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "shopping_list_recipe_reference" ADD CONSTRAINT "fk_shopping_shopping_380c9d9c" FOREIGN KEY ("shopping_list_id") REFERENCES "shopping_lists" ("id") ON DELETE RESTRICT;
ALTER TABLE "webhook_urls" ADD CONSTRAINT "fk_webhook__groups_671aef15" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "webhook_urls" ADD CONSTRAINT "fk_webhook__househol_a3fab964" FOREIGN KEY ("household_id") REFERENCES "households" ("id") ON DELETE RESTRICT;
ALTER TABLE "api_extras" ADD CONSTRAINT "fk_api_extr_recipes_4cdbd043" FOREIGN KEY ("recipee_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_food_extras" ADD CONSTRAINT "fk_ingredie_ingredie_63129750" FOREIGN KEY ("ingredient_food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_assets" ADD CONSTRAINT "fk_recipe_a_recipes_d1e7b857" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "categories" ADD CONSTRAINT "fk_categori_groups_e0bdf409" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_comments" ADD CONSTRAINT "fk_recipe_c_recipes_9358aafb" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_comments" ADD CONSTRAINT "fk_recipe_c_users_47a2331d" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_foods_aliases" ADD CONSTRAINT "fk_ingredie_ingredie_847d2f2f" FOREIGN KEY ("food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_foods" ADD CONSTRAINT "fk_ingredie_groups_a1a6deb3" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_foods" ADD CONSTRAINT "fk_ingredie_multi_pu_c9300620" FOREIGN KEY ("label_id") REFERENCES "multi_purpose_labels" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_foods_substitutions" ADD CONSTRAINT "fk_ingredie_ingredie_0eabfd9d" FOREIGN KEY ("food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_foods_substitutions" ADD CONSTRAINT "fk_ingredie_ingredie_9189d450" FOREIGN KEY ("substitute_food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_units_aliases" ADD CONSTRAINT "fk_ingredie_ingredie_e5bed4a9" FOREIGN KEY ("unit_id") REFERENCES "ingredient_units" ("id") ON DELETE RESTRICT;
ALTER TABLE "ingredient_units" ADD CONSTRAINT "fk_ingredie_groups_a414155c" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes_ingredients" ADD CONSTRAINT "fk_recipes__ingredie_6bbdbf20" FOREIGN KEY ("food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes_ingredients" ADD CONSTRAINT "fk_recipes__recipes_edebb88e" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes_ingredients" ADD CONSTRAINT "fk_recipes__recipes_421d580d" FOREIGN KEY ("referenced_recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes_ingredients" ADD CONSTRAINT "fk_recipes__ingredie_442e6861" FOREIGN KEY ("unit_id") REFERENCES "ingredient_units" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes_ingredients_substitutions" ADD CONSTRAINT "fk_recipes__recipes__0a708a06" FOREIGN KEY ("ingredient_id") REFERENCES "recipes_ingredients" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes_ingredients_substitutions" ADD CONSTRAINT "fk_recipes__ingredie_91ae5bc7" FOREIGN KEY ("substitute_food_id") REFERENCES "ingredient_foods" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_ingredient_ref_link" ADD CONSTRAINT "fk_recipe_i_recipe_i_29cb08c7" FOREIGN KEY ("instruction_id") REFERENCES "recipe_instructions" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_instructions" ADD CONSTRAINT "fk_recipe_i_recipes_bfb090ca" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_note_ref_link" ADD CONSTRAINT "fk_recipe_n_recipe_i_47395764" FOREIGN KEY ("instruction_id") REFERENCES "recipe_instructions" ("id") ON DELETE RESTRICT;
ALTER TABLE "multi_purpose_labels" ADD CONSTRAINT "fk_multi_pu_groups_80b73274" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "notes" ADD CONSTRAINT "fk_notes_recipes_eef9e69f" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_nutrition" ADD CONSTRAINT "fk_recipe_n_recipes_51cb1b51" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes" ADD CONSTRAINT "fk_recipes_groups_56fd3926" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipes" ADD CONSTRAINT "fk_recipes_users_1fec4c7a" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_timeline_events" ADD CONSTRAINT "fk_recipe_t_recipes_286e3649" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_timeline_events" ADD CONSTRAINT "fk_recipe_t_users_3a21d8c1" FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_settings" ADD CONSTRAINT "fk_recipe_s_recipes_ce13719d" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_share_tokens" ADD CONSTRAINT "fk_recipe_s_groups_4a824efe" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "recipe_share_tokens" ADD CONSTRAINT "fk_recipe_s_recipes_a19ef3a3" FOREIGN KEY ("recipe_id") REFERENCES "recipes" ("id") ON DELETE RESTRICT;
ALTER TABLE "tags" ADD CONSTRAINT "fk_tags_groups_6178e62f" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
ALTER TABLE "tools" ADD CONSTRAINT "fk_tools_groups_3f636859" FOREIGN KEY ("group_id") REFERENCES "groups" ("id") ON DELETE RESTRICT;
CREATE INDEX "ix_recipes_name_normalized_gin" ON "recipes" USING gin ("name_normalized" gin_trgm_ops);
CREATE INDEX "ix_recipes_description_normalized_gin" ON "recipes" USING gin ("description_normalized" gin_trgm_ops);
CREATE INDEX "ix_recipes_ingredients_note_normalized_gin" ON "recipes_ingredients" USING gin ("note_normalized" gin_trgm_ops);
CREATE INDEX "ix_recipes_ingredients_original_text_normalized_gin" ON "recipes_ingredients" USING gin ("original_text_normalized" gin_trgm_ops);
CREATE TABLE "aerich" ("id" SERIAL PRIMARY KEY NOT NULL, "version" VARCHAR(255) NOT NULL, "app" VARCHAR(100) NOT NULL, "content" JSONB NOT NULL);
