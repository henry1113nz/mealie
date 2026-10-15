"""Tortoise mappings for the remaining legacy model graph (Stage 5)."""

from datetime import UTC, datetime
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

from ._base import MealieUUIDField


class AIProviderHeaders(Model):
    provider = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="ai_provider_headers_provider_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="provider_id",
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "ai_provider_headers"


class AIProviderParams(Model):
    provider = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="ai_provider_params_provider_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="provider_id",
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "ai_provider_params"


class AIProvider(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    settings = fields.ForeignKeyField(
        "models.AIProviderSettings",
        related_name="ai_providers_settings_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="settings_id",
        db_index=True,
    )
    name = fields.CharField(max_length=255, db_index=True)
    base_url = fields.TextField(null=True)
    api_key = fields.TextField()
    model = fields.TextField()
    timeout = fields.IntField(default=300)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "ai_providers"
        unique_together = (("name", "settings"),)


class AIProviderSettings(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="ai_provider_settings_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
        unique=True,
    )
    default_provider = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="default_for_settings",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="default_provider_id",
        null=True,
        db_index=True,
        db_constraint=False,
    )
    audio_provider = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="audio_for_settings",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="audio_provider_id",
        null=True,
        db_index=True,
        db_constraint=False,
    )
    image_provider = fields.ForeignKeyField(
        "models.AIProvider",
        related_name="image_for_settings",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="image_provider_id",
        null=True,
        db_index=True,
        db_constraint=False,
    )
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "ai_provider_settings"


class GroupDataExportsModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_data_exports_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    name = fields.TextField()
    filename = fields.TextField()
    path = fields.TextField()
    size = fields.TextField()
    expires = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_data_exports"


class ApiExtras(Model):
    recipee = fields.ForeignKeyField(
        "models.Recipe",
        related_name="api_extras_recipee_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipee_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "api_extras"


class IngredientFoodExtras(Model):
    ingredient_food = fields.ForeignKeyField(
        "models.IngredientFood",
        related_name="ingredient_food_extras_ingredient_food_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="ingredient_food_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "ingredient_food_extras"


class ShoppingListExtras(Model):
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="shopping_list_extras_shopping_list_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="shopping_list_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_list_extras"


class ShoppingListItemExtras(Model):
    shopping_list_item = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="shopping_list_item_extras_shopping_list_item_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="shopping_list_item_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_list_item_extras"


class RecipeAsset(Model):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_assets_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    name = fields.TextField(null=True)
    icon = fields.TextField(null=True)
    file_name = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_assets"


class GroupToCategories(Model):
    row_id = fields.IntField(primary_key=True)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_to_categories_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    category = fields.ForeignKeyField(
        "models.Category",
        related_name="group_to_categories_category_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="category_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "group_to_categories"
        unique_together = (("group", "category"),)


class PlanRulesToCategories(Model):
    row_id = fields.IntField(primary_key=True)
    group_plan_rule = fields.ForeignKeyField(
        "models.GroupMealPlanRules",
        related_name="plan_rules_to_categories_group_plan_rule_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_plan_rule_id",
        null=True,
        db_index=True,
    )
    category = fields.ForeignKeyField(
        "models.Category",
        related_name="plan_rules_to_categories_category_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="category_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "plan_rules_to_categories"
        unique_together = (("group_plan_rule", "category"),)


class RecipesToCategories(Model):
    row_id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipes_to_categories_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    category = fields.ForeignKeyField(
        "models.Category",
        related_name="recipes_to_categories_category_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="category_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "recipes_to_categories"
        unique_together = (("recipe", "category"),)


class CookbooksToCategories(Model):
    row_id = fields.IntField(primary_key=True)
    cookbook = fields.ForeignKeyField(
        "models.CookBook",
        related_name="cookbooks_to_categories_cookbook_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="cookbook_id",
        null=True,
        db_index=True,
    )
    category = fields.ForeignKeyField(
        "models.Category",
        related_name="cookbooks_to_categories_category_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="category_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "cookbooks_to_categories"
        unique_together = (("cookbook", "category"),)


class Category(Model):
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="categories_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    id = MealieUUIDField(primary_key=True, default=uuid4)
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "categories"
        unique_together = (("slug", "group"),)


class RecipeComment(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    text = fields.TextField(null=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_comments_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        db_index=True,
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="recipe_comments_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        db_index=True,
    )
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_comments"


class MultiPurposeLabel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    name = fields.CharField(max_length=255)
    color = fields.CharField(max_length=10, default="")
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="multi_purpose_labels_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "multi_purpose_labels"
        unique_together = (("name", "group"),)


class RecipeIngredientRefLink(Model):
    instruction = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="recipe_ingredient_ref_link_instruction_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="instruction_id",
        null=True,
        db_index=True,
    )
    reference_id = MealieUUIDField(null=True, db_index=True, default=uuid4)
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_ingredient_ref_link"


class RecipeNoteRefLink(Model):
    instruction = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="recipe_note_ref_link_instruction_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="instruction_id",
        null=True,
        db_index=True,
    )
    reference_id = MealieUUIDField(null=True, db_index=True, default=uuid4)
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_note_ref_link"


class RecipeInstruction(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_instructions_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    position = fields.IntField(null=True, db_index=True)
    type = fields.TextField(null=True, default="")
    title = fields.TextField(null=True)
    text = fields.TextField(null=True)
    summary = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_instructions"


class Note(Model):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="notes_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    title = fields.TextField(null=True)
    text = fields.TextField(null=True)
    reference_id = MealieUUIDField(null=True, db_index=True, default=uuid4)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "notes"


class RecipesToTags(Model):
    row_id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipes_to_tags_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    tag = fields.ForeignKeyField(
        "models.Tag",
        related_name="recipes_to_tags_tag_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="tag_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "recipes_to_tags"
        unique_together = (("recipe", "tag"),)


class PlanRulesToTags(Model):
    row_id = fields.IntField(primary_key=True)
    plan_rule = fields.ForeignKeyField(
        "models.GroupMealPlanRules",
        related_name="plan_rules_to_tags_plan_rule_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="plan_rule_id",
        null=True,
        db_index=True,
    )
    tag = fields.ForeignKeyField(
        "models.Tag",
        related_name="plan_rules_to_tags_tag_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="tag_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "plan_rules_to_tags"
        unique_together = (("plan_rule", "tag"),)


class CookbooksToTags(Model):
    row_id = fields.IntField(primary_key=True)
    cookbook = fields.ForeignKeyField(
        "models.CookBook",
        related_name="cookbooks_to_tags_cookbook_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="cookbook_id",
        null=True,
        db_index=True,
    )
    tag = fields.ForeignKeyField(
        "models.Tag",
        related_name="cookbooks_to_tags_tag_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="tag_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "cookbooks_to_tags"
        unique_together = (("cookbook", "tag"),)


class Tag(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="tags_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "tags"
        unique_together = (("slug", "group"),)


class HouseholdsToTools(Model):
    row_id = fields.IntField(primary_key=True)
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="households_to_tools_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    tool = fields.ForeignKeyField(
        "models.Tool",
        related_name="households_to_tools_tool_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="tool_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "households_to_tools"
        unique_together = (("household", "tool"),)


class RecipesToTools(Model):
    row_id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipes_to_tools_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    tool = fields.ForeignKeyField(
        "models.Tool",
        related_name="recipes_to_tools_tool_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="tool_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "recipes_to_tools"
        unique_together = (("recipe", "tool"),)


class CookbooksToTools(Model):
    row_id = fields.IntField(primary_key=True)
    cookbook = fields.ForeignKeyField(
        "models.CookBook",
        related_name="cookbooks_to_tools_cookbook_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="cookbook_id",
        null=True,
        db_index=True,
    )
    tool = fields.ForeignKeyField(
        "models.Tool",
        related_name="cookbooks_to_tools_tool_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="tool_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "cookbooks_to_tools"
        unique_together = (("cookbook", "tool"),)


class Tool(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="tools_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, db_index=True)
    on_hand = fields.BooleanField(null=True, default=False)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "tools"
        unique_together = (("slug", "group"),)


class CookBook(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    position = fields.IntField(default=1)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="cookbooks_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="cookbooks_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    name = fields.TextField()
    slug = fields.CharField(max_length=255, db_index=True)
    description = fields.TextField(null=True, default="")
    public = fields.BooleanField(null=True, default=False)
    query_filter_string = fields.TextField(default="")
    require_all_categories = fields.BooleanField(null=True, default=True)
    require_all_tags = fields.BooleanField(null=True, default=True)
    require_all_tools = fields.BooleanField(null=True, default=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "cookbooks"
        unique_together = (("slug", "group"),)


class GroupEventNotifierOptionsModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    event_notifier = fields.ForeignKeyField(
        "models.GroupEventNotifierModel",
        related_name="group_events_notifier_options_event_notifier_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="event_notifier_id",
    )
    recipe_created = fields.BooleanField(default=False)
    recipe_updated = fields.BooleanField(default=False)
    recipe_deleted = fields.BooleanField(default=False)
    user_signup = fields.BooleanField(default=False)
    data_migrations = fields.BooleanField(default=False)
    data_export = fields.BooleanField(default=False)
    data_import = fields.BooleanField(default=False)
    mealplan_entry_created = fields.BooleanField(default=False)
    mealplan_entry_updated = fields.BooleanField(default=False)
    mealplan_entry_deleted = fields.BooleanField(default=False)
    shopping_list_created = fields.BooleanField(default=False)
    shopping_list_updated = fields.BooleanField(default=False)
    shopping_list_deleted = fields.BooleanField(default=False)
    cookbook_created = fields.BooleanField(default=False)
    cookbook_updated = fields.BooleanField(default=False)
    cookbook_deleted = fields.BooleanField(default=False)
    tag_created = fields.BooleanField(default=False)
    tag_updated = fields.BooleanField(default=False)
    tag_deleted = fields.BooleanField(default=False)
    category_created = fields.BooleanField(default=False)
    category_updated = fields.BooleanField(default=False)
    category_deleted = fields.BooleanField(default=False)
    label_created = fields.BooleanField(default=False)
    label_updated = fields.BooleanField(default=False)
    label_deleted = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_events_notifier_options"


class GroupEventNotifierModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    name = fields.TextField()
    enabled = fields.BooleanField(default=True)
    apprise_url = fields.TextField()
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_events_notifiers_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="group_events_notifiers_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_events_notifiers"


class HouseholdToRecipe(Model):
    row_id = fields.IntField(primary_key=True)
    id = MealieUUIDField(default=uuid4)
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="households_to_recipes_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        db_index=True,
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="households_to_recipes_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        db_index=True,
    )
    last_made = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "households_to_recipes"
        unique_together = (("id", "household", "recipe"), ("household", "recipe"))


class GroupInviteToken(Model):
    token = fields.CharField(max_length=255, db_index=True, unique=True)
    uses_left = fields.IntField(default=1)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="invite_tokens_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="invite_tokens_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "invite_tokens"


class PlanRulesToHouseholds(Model):
    row_id = fields.IntField(primary_key=True)
    group_plan_rule = fields.ForeignKeyField(
        "models.GroupMealPlanRules",
        related_name="plan_rules_to_households_group_plan_rule_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_plan_rule_id",
        null=True,
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="plan_rules_to_households_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )

    class Meta:
        table = "plan_rules_to_households"
        unique_together = (("group_plan_rule", "household"),)


class GroupMealPlanRules(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_meal_plan_rules_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="group_meal_plan_rules_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    day = fields.TextField(default="unset")
    entry_type = fields.TextField(default="")
    query_filter_string = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_meal_plan_rules"


class GroupMealPlan(Model):
    date = fields.DateField(db_index=True)
    entry_type = fields.CharField(max_length=255, db_index=True)
    title = fields.CharField(max_length=255, db_index=True)
    text = fields.TextField()
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_meal_plans_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="group_meal_plans_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        null=True,
        db_index=True,
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="group_meal_plans_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_meal_plans"


class HouseholdPreferencesModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="household_preferences_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        db_index=True,
    )
    private_household = fields.BooleanField(null=True, default=True)
    show_announcements = fields.BooleanField(default=True)
    lock_recipe_edits_from_other_households = fields.BooleanField(null=True, default=True)
    first_day_of_week = fields.IntField(null=True, default=0)
    recipe_public = fields.BooleanField(null=True, default=True)
    recipe_show_nutrition = fields.BooleanField(null=True, default=False)
    recipe_show_assets = fields.BooleanField(null=True, default=False)
    recipe_landscape_view = fields.BooleanField(null=True, default=False)
    recipe_disable_comments = fields.BooleanField(null=True, default=False)
    recipe_disable_amount = fields.BooleanField(null=True, default=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "household_preferences"


class GroupRecipeAction(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="recipe_actions_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="recipe_actions_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    action_type = fields.CharField(max_length=255, db_index=True)
    title = fields.CharField(max_length=255, db_index=True)
    url = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_actions"


class ShoppingListItemRecipeReference(Model):
    row_id = fields.IntField(primary_key=True)
    id = MealieUUIDField(default=uuid4)
    shopping_list_item = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="shopping_list_item_recipe_reference_shopping_list_item_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="shopping_list_item_id",
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="shopping_list_item_recipe_reference_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    recipe_quantity = fields.FloatField()
    recipe_scale = fields.FloatField(default=1)
    recipe_note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_list_item_recipe_reference"
        unique_together = (("id", "shopping_list_item"),)


class ShoppingListItem(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="shopping_list_items_shopping_list_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="shopping_list_id",
        null=True,
        db_index=True,
    )
    is_ingredient = fields.BooleanField(null=True, default=True)
    position = fields.IntField(db_index=True, default=0)
    checked = fields.BooleanField(null=True, default=False)
    quantity = fields.FloatField(null=True, default=1)
    note = fields.TextField(null=True)
    unit = fields.ForeignKeyField(
        "models.IngredientUnit",
        related_name="shopping_list_items_unit_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="unit_id",
        null=True,
    )
    food = fields.ForeignKeyField(
        "models.IngredientFood",
        related_name="shopping_list_items_food_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="food_id",
        null=True,
    )
    label = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_list_items_label_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="label_id",
        null=True,
    )
    is_food = fields.BooleanField(null=True, default=False)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_list_items"


class ShoppingListRecipeReference(Model):
    row_id = fields.IntField(primary_key=True)
    id = MealieUUIDField(default=uuid4)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="shopping_list_recipe_reference_shopping_list_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="shopping_list_id",
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="shopping_list_recipe_reference_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    recipe_quantity = fields.FloatField()
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_list_recipe_reference"
        unique_together = (("id", "shopping_list"),)


class ShoppingListMultiPurposeLabel(Model):
    row_id = fields.IntField(primary_key=True)
    id = MealieUUIDField(default=uuid4)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="shopping_lists_multi_purpose_labels_shopping_list_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="shopping_list_id",
    )
    label = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_lists_multi_purpose_labels_label_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="label_id",
    )
    position = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_lists_multi_purpose_labels"
        unique_together = (("id", "shopping_list", "label"), ("shopping_list", "label"))


class ShoppingList(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="shopping_lists_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="shopping_lists_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        db_index=True,
    )
    name = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "shopping_lists"


class GroupWebhooksModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="webhook_urls_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        null=True,
        db_index=True,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="webhook_urls_household_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="household_id",
        null=True,
        db_index=True,
    )
    enabled = fields.BooleanField(null=True, default=False)
    name = fields.TextField(null=True)
    url = fields.TextField(null=True)
    webhook_type = fields.TextField(null=True, default="")
    scheduled_time = fields.TimeField(null=True)
    time = fields.TextField(null=True, default="00:00")
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "webhook_urls"


class PasswordResetModel(Model):
    user = fields.ForeignKeyField(
        "models.User",
        related_name="password_reset_tokens_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        db_index=True,
    )
    token = fields.CharField(max_length=64, unique=True)
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "password_reset_tokens"


class UserToRecipe(Model):
    row_id = fields.IntField(primary_key=True)
    id = MealieUUIDField(default=uuid4)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="users_to_recipes_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        db_index=True,
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="users_to_recipes_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        db_index=True,
    )
    rating = fields.FloatField(null=True, db_index=True)
    is_favorite = fields.BooleanField(db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "users_to_recipes"
        unique_together = (("id", "user", "recipe"), ("user", "recipe"))


class LongLiveToken(Model):
    name = fields.TextField()
    token = fields.CharField(max_length=512, db_index=True)
    user = fields.ForeignKeyField(
        "models.User",
        related_name="long_live_tokens_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        null=True,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "long_live_tokens"


class RecipeTimelineEvent(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_timeline_events_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        db_index=True,
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="recipe_timeline_events_user_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="user_id",
        db_index=True,
    )
    subject = fields.TextField()
    message = fields.TextField(null=True)
    event_type = fields.TextField(null=True)
    image = fields.TextField(null=True)
    timestamp = fields.DatetimeField(null=True, db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_timeline_events"


class RecipeSettings(Model):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_settings_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        null=True,
        db_index=True,
    )
    public = fields.BooleanField(null=True)
    show_nutrition = fields.BooleanField(null=True)
    show_assets = fields.BooleanField(null=True)
    landscape_view = fields.BooleanField(null=True)
    disable_comments = fields.BooleanField(null=True, default=False)
    locked = fields.BooleanField(null=True, default=False)
    disable_amount = fields.BooleanField(null=True, default=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_settings"


class RecipeShareTokenModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="recipe_share_tokens_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_share_tokens_recipe_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="recipe_id",
        db_index=True,
    )
    expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "recipe_share_tokens"


class ServerTaskModel(Model):
    name = fields.TextField()
    completed_date = fields.DatetimeField(null=True)
    status = fields.TextField()
    log = fields.TextField(null=True)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="server_tasks_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "server_tasks"


class GroupPreferencesModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_preferences_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    private_group = fields.BooleanField(null=True, default=True)
    show_announcements = fields.BooleanField(default=True)
    first_day_of_week = fields.IntField(null=True, default=0)
    recipe_public = fields.BooleanField(null=True, default=True)
    recipe_show_nutrition = fields.BooleanField(null=True, default=False)
    recipe_show_assets = fields.BooleanField(null=True, default=False)
    recipe_landscape_view = fields.BooleanField(null=True, default=False)
    recipe_disable_comments = fields.BooleanField(null=True, default=False)
    recipe_disable_amount = fields.BooleanField(null=True, default=True)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_preferences"


class ReportEntryModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    success = fields.BooleanField(null=True, default=False)
    message = fields.TextField(null=True)
    exception = fields.TextField(null=True)
    timestamp = fields.DatetimeField(default=lambda: datetime.now(UTC))
    report = fields.ForeignKeyField(
        "models.ReportModel",
        related_name="report_entries_report_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="report_id",
        db_index=True,
    )
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "report_entries"


class ReportModel(Model):
    id = MealieUUIDField(primary_key=True, default=uuid4)
    name = fields.TextField()
    status = fields.TextField()
    category = fields.CharField(max_length=255, db_index=True)
    timestamp = fields.DatetimeField(default=lambda: datetime.now(UTC))
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_reports_group_id_related",
        on_delete=fields.OnDelete.NO_ACTION,
        source_field="group_id",
        db_index=True,
    )
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        table = "group_reports"


__all__ = [
    "AIProviderHeaders",
    "AIProviderParams",
    "AIProvider",
    "AIProviderSettings",
    "GroupDataExportsModel",
    "ApiExtras",
    "IngredientFoodExtras",
    "ShoppingListExtras",
    "ShoppingListItemExtras",
    "RecipeAsset",
    "GroupToCategories",
    "PlanRulesToCategories",
    "RecipesToCategories",
    "CookbooksToCategories",
    "Category",
    "RecipeComment",
    "MultiPurposeLabel",
    "RecipeIngredientRefLink",
    "RecipeNoteRefLink",
    "RecipeInstruction",
    "Note",
    "RecipesToTags",
    "PlanRulesToTags",
    "CookbooksToTags",
    "Tag",
    "HouseholdsToTools",
    "RecipesToTools",
    "CookbooksToTools",
    "Tool",
    "CookBook",
    "GroupEventNotifierOptionsModel",
    "GroupEventNotifierModel",
    "HouseholdToRecipe",
    "GroupInviteToken",
    "PlanRulesToHouseholds",
    "GroupMealPlanRules",
    "GroupMealPlan",
    "HouseholdPreferencesModel",
    "GroupRecipeAction",
    "ShoppingListItemRecipeReference",
    "ShoppingListItem",
    "ShoppingListRecipeReference",
    "ShoppingListMultiPurposeLabel",
    "ShoppingList",
    "GroupWebhooksModel",
    "PasswordResetModel",
    "UserToRecipe",
    "LongLiveToken",
    "RecipeTimelineEvent",
    "RecipeSettings",
    "RecipeShareTokenModel",
    "ServerTaskModel",
    "GroupPreferencesModel",
    "ReportEntryModel",
    "ReportModel",
]
