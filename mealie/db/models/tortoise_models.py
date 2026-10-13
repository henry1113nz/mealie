"""Tortoise ORM model registry.

The application model set is being moved here in groups. Keep table and source
field names aligned with the existing SQLite and PostgreSQL schema.
"""

from datetime import UTC, datetime
from datetime import date as Date
from enum import StrEnum
from uuid import UUID, uuid4

from tortoise import Model, fields


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GUIDField(fields.CharField):
    """UUID field matching Mealie's 32 character SQLite representation."""

    SQL_TYPE = "CHAR(32)"

    class _db_postgres:
        SQL_TYPE = "UUID"

    def to_db_value(self, value, instance):
        if value is None:
            return None
        return UUID(str(value)).hex

    def to_python_value(self, value):
        if value is None or isinstance(value, UUID):
            return value
        return UUID(str(value))


class TortoiseBase(Model):
    created_at = fields.DatetimeField(null=True, default=utc_now, db_index=True)
    update_at = fields.DatetimeField(null=True, default=utc_now, auto_now=True)

    @property
    def updated_at(self) -> datetime | None:
        return self.update_at

    class Meta:
        abstract = True


class Group(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    name = fields.CharField(max_length=255, unique=True, db_index=True)
    slug = fields.CharField(max_length=255, null=True, unique=True, db_index=True)
    categories = fields.ManyToManyField(
        "models.Category",
        through="group_to_categories",
        forward_key="category_id",
        backward_key="group_id",
        related_name="groups",
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "groups"


class Household(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, null=True, db_index=True)
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="households",
        source_field="group_id",
        on_delete=fields.NO_ACTION,
    )
    ingredient_foods_on_hand = fields.ManyToManyField(
        "models.IngredientFoodModel",
        through="households_to_ingredient_foods",
        forward_key="food_id",
        backward_key="household_id",
        related_name="households_with_ingredient_food",
        on_delete=fields.NO_ACTION,
    )
    tools_on_hand = fields.ManyToManyField(
        "models.Tool",
        through="households_to_tools",
        forward_key="tool_id",
        backward_key="household_id",
        related_name="households_with_tool",
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "households"
        unique_together = (("group", "name"), ("group", "slug"))


class AuthMethod(StrEnum):
    MEALIE = "MEALIE"
    LDAP = "LDAP"
    OIDC = "OIDC"


class User(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    full_name = fields.CharField(max_length=255, null=True, db_index=True)
    username = fields.CharField(max_length=255, null=True, unique=True, db_index=True)
    email = fields.CharField(max_length=255, null=True, unique=True, db_index=True)
    password = fields.TextField(null=True)
    auth_method = fields.CharField(max_length=6, default=AuthMethod.MEALIE.value)
    admin = fields.BooleanField(null=True, default=False)
    advanced = fields.BooleanField(null=True, default=False)
    group = fields.ForeignKeyField(
        "models.Group", related_name="users", source_field="group_id", on_delete=fields.NO_ACTION
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="users",
        source_field="household_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    cache_key = fields.CharField(max_length=255, null=True, default="1234")
    external_avatar_hash = fields.CharField(max_length=255, null=True)
    login_attemps = fields.IntField(null=True, default=0)
    locked_at = fields.DatetimeField(null=True)
    tokens_valid_after = fields.DatetimeField(null=True)
    show_announcements = fields.BooleanField(default=True)
    last_read_announcement = fields.CharField(max_length=255, null=True)
    can_manage_household = fields.BooleanField(null=True, default=False)
    can_manage = fields.BooleanField(null=True, default=False)
    can_invite = fields.BooleanField(null=True, default=False)
    can_organize = fields.BooleanField(null=True, default=False)
    owned_recipes_id = GUIDField(max_length=32, null=True)

    class Meta:
        table = "users"

    @property
    def is_admin(self) -> bool:
        return bool(self.admin)


class LongLiveToken(TortoiseBase):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    token = fields.CharField(max_length=255, db_index=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="tokens", source_field="user_id", null=True, on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "long_live_tokens"


class PasswordResetModel(TortoiseBase):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="password_reset_tokens", source_field="user_id", on_delete=fields.NO_ACTION
    )
    token = fields.CharField(max_length=64, unique=True)

    class Meta:
        table = "password_reset_tokens"


class Recipe(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    slug = fields.CharField(max_length=255, null=True, db_index=True)
    group = fields.ForeignKeyField(
        "models.Group", related_name="recipes", source_field="group_id", on_delete=fields.NO_ACTION
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="recipes", source_field="user_id", null=True, on_delete=fields.NO_ACTION
    )
    recipe_category = fields.ManyToManyField(
        "models.Category",
        through="recipes_to_categories",
        forward_key="category_id",
        backward_key="recipe_id",
        related_name="recipes",
        on_delete=fields.NO_ACTION,
    )
    tags = fields.ManyToManyField(
        "models.Tag",
        through="recipes_to_tags",
        forward_key="tag_id",
        backward_key="recipe_id",
        related_name="recipes",
        on_delete=fields.NO_ACTION,
    )
    tools = fields.ManyToManyField(
        "models.Tool",
        through="recipes_to_tools",
        forward_key="tool_id",
        backward_key="recipe_id",
        related_name="recipes",
        on_delete=fields.NO_ACTION,
    )
    rating = fields.FloatField(null=True, db_index=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    image = fields.CharField(max_length=1024, null=True)
    total_time = fields.CharField(max_length=255, null=True)
    prep_time = fields.CharField(max_length=255, null=True)
    perform_time = fields.CharField(max_length=255, null=True)
    total_time_seconds = fields.IntField(null=True)
    prep_time_seconds = fields.IntField(null=True)
    perform_time_seconds = fields.IntField(null=True)
    recipe_yield = fields.CharField(max_length=255, null=True)
    recipe_yield_quantity = fields.FloatField(default=0, db_index=True)
    recipe_servings = fields.FloatField(default=0, db_index=True)
    org_url = fields.CharField(max_length=2048, null=True)
    date_added = fields.DateField(null=True, default=Date.today)
    date_updated = fields.DatetimeField(null=True)
    last_made = fields.DatetimeField(null=True)
    name_normalized = fields.CharField(max_length=255, db_index=True)
    description_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    cook_time = fields.CharField(max_length=255, null=True)
    recipeCuisine = fields.CharField(max_length=255, null=True)
    is_ocr_recipe = fields.BooleanField(null=True, default=False)

    class Meta:
        table = "recipes"
        unique_together = (("slug", "group"),)


class RecipeAsset(TortoiseBase):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="assets", source_field="recipe_id", null=True, on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, null=True)
    icon = fields.CharField(max_length=255, null=True)
    file_name = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "recipe_assets"


class Nutrition(TortoiseBase):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="nutrition_entries",
        source_field="recipe_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    calories = fields.CharField(max_length=255, null=True)
    carbohydrate_content = fields.CharField(max_length=255, null=True)
    cholesterol_content = fields.CharField(max_length=255, null=True)
    fat_content = fields.CharField(max_length=255, null=True)
    fiber_content = fields.CharField(max_length=255, null=True)
    protein_content = fields.CharField(max_length=255, null=True)
    saturated_fat_content = fields.CharField(max_length=255, null=True)
    sodium_content = fields.CharField(max_length=255, null=True)
    sugar_content = fields.CharField(max_length=255, null=True)
    trans_fat_content = fields.CharField(max_length=255, null=True)
    unsaturated_fat_content = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "recipe_nutrition"


class RecipeSettings(TortoiseBase):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="settings_entries",
        source_field="recipe_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    public = fields.BooleanField(null=True)
    show_nutrition = fields.BooleanField(null=True)
    show_assets = fields.BooleanField(null=True)
    landscape_view = fields.BooleanField(null=True)
    disable_comments = fields.BooleanField(null=True, default=False)
    locked = fields.BooleanField(null=True, default=False)
    disable_amount = fields.BooleanField(null=True, default=True)

    class Meta:
        table = "recipe_settings"


class Note(TortoiseBase):
    id = fields.IntField(primary_key=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="notes", source_field="recipe_id", null=True, on_delete=fields.NO_ACTION
    )
    title = fields.CharField(max_length=255, null=True)
    text = fields.TextField(null=True)
    reference_id = GUIDField(max_length=32, null=True, default=uuid4)

    class Meta:
        table = "notes"


class RecipeInstruction(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="recipe_instructions",
        source_field="recipe_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    position = fields.IntField(null=True, db_index=True)
    type = fields.CharField(max_length=255, null=True, default="")
    title = fields.CharField(max_length=255, null=True)
    text = fields.TextField(null=True)
    summary = fields.TextField(null=True)

    class Meta:
        table = "recipe_instructions"


class RecipeIngredientRefLink(TortoiseBase):
    id = fields.IntField(primary_key=True)
    instruction = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="ingredient_references",
        source_field="instruction_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    reference_id = GUIDField(max_length=32, null=True, db_index=True)

    class Meta:
        table = "recipe_ingredient_ref_link"


class RecipeNoteRefLink(TortoiseBase):
    id = fields.IntField(primary_key=True)
    instruction = fields.ForeignKeyField(
        "models.RecipeInstruction",
        related_name="note_references",
        source_field="instruction_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    reference_id = GUIDField(max_length=32, null=True, db_index=True)

    class Meta:
        table = "recipe_note_ref_link"


class RecipeComment(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    text = fields.TextField(null=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="comments", source_field="recipe_id", on_delete=fields.NO_ACTION
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="comments", source_field="user_id", on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "recipe_comments"


class RecipeShareTokenModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="recipe_share_tokens", source_field="group_id", on_delete=fields.NO_ACTION
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="share_tokens", source_field="recipe_id", on_delete=fields.NO_ACTION
    )
    expires_at = fields.DatetimeField()

    class Meta:
        table = "recipe_share_tokens"


class RecipeTimelineEvent(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="timeline_events", source_field="recipe_id", on_delete=fields.NO_ACTION
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="recipe_timeline_events", source_field="user_id", on_delete=fields.NO_ACTION
    )
    subject = fields.CharField(max_length=255)
    message = fields.TextField(null=True)
    event_type = fields.CharField(max_length=255, null=True)
    image = fields.CharField(max_length=1024, null=True)
    timestamp = fields.DatetimeField(null=True, db_index=True)

    class Meta:
        table = "recipe_timeline_events"


class MultiPurposeLabel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    name = fields.CharField(max_length=255)
    color = fields.CharField(max_length=10, default="")
    group = fields.ForeignKeyField(
        "models.Group", related_name="labels", source_field="group_id", on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "multi_purpose_labels"
        unique_together = (("name", "group"),)


class IngredientUnitModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="ingredient_units", source_field="group_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, null=True)
    plural_name = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    abbreviation = fields.CharField(max_length=255, null=True)
    plural_abbreviation = fields.CharField(max_length=255, null=True)
    use_abbreviation = fields.BooleanField(null=True, default=False)
    fraction = fields.BooleanField(null=True, default=True)
    standard_quantity = fields.FloatField(null=True)
    standard_unit = fields.CharField(max_length=255, null=True)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    abbreviation_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_abbreviation_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_units"


class IngredientFoodModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="ingredient_foods", source_field="group_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, null=True)
    plural_name = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    label = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="foods",
        source_field="label_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    on_hand = fields.BooleanField(default=False)

    class Meta:
        table = "ingredient_foods"


class IngredientUnitAliasModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    unit = fields.ForeignKeyField(
        "models.IngredientUnitModel", related_name="aliases", source_field="unit_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_units_aliases"
        unique_together = (("id", "unit"),)


class IngredientFoodAliasModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    food = fields.ForeignKeyField(
        "models.IngredientFoodModel", related_name="aliases", source_field="food_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_aliases"
        unique_together = (("id", "food"),)


class IngredientFoodSubstitutionModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    food = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="substitutions",
        source_field="food_id",
        on_delete=fields.NO_ACTION,
    )
    substitute_food = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="substitution_references",
        source_field="substitute_food_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    note = fields.TextField(null=True)
    position = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_substitutions"
        unique_together = (("food", "substitute_food"),)


class RecipeIngredientModel(TortoiseBase):
    id = fields.IntField(primary_key=True)
    position = fields.IntField(null=True, db_index=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="ingredients", source_field="recipe_id", null=True, on_delete=fields.NO_ACTION
    )
    title = fields.CharField(max_length=255, null=True)
    note = fields.TextField(null=True)
    unit = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="ingredients",
        source_field="unit_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    food = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="ingredients",
        source_field="food_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    quantity = fields.FloatField(null=True)
    original_text = fields.TextField(null=True)
    reference_id = GUIDField(max_length=32, null=True)
    referenced_recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="referenced_ingredients",
        source_field="referenced_recipe_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    note_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    original_text_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients"


class RecipeIngredientSubstitutionModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    ingredient = fields.ForeignKeyField(
        "models.RecipeIngredientModel",
        related_name="substitutions",
        source_field="ingredient_id",
        on_delete=fields.NO_ACTION,
    )
    substitute_food = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="recipe_substitution_references",
        source_field="substitute_food_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    note = fields.TextField(null=True)
    position = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients_substitutions"


class GroupPreferencesModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="preferences_rows", source_field="group_id", on_delete=fields.NO_ACTION
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

    class Meta:
        table = "group_preferences"


class HouseholdPreferencesModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    household = fields.ForeignKeyField(
        "models.Household", related_name="preferences_rows", source_field="household_id", on_delete=fields.NO_ACTION
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

    class Meta:
        table = "household_preferences"


class AIProviderSettings(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="ai_provider_settings_rows", source_field="group_id", on_delete=fields.NO_ACTION
    )
    default_provider_id = GUIDField(max_length=32, null=True)
    audio_provider_id = GUIDField(max_length=32, null=True)
    image_provider_id = GUIDField(max_length=32, null=True)

    class Meta:
        table = "ai_provider_settings"
        unique_together = (("group",),)


class AIProvider(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    settings = fields.ForeignKeyField(
        "models.AIProviderSettings", related_name="providers", source_field="settings_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, db_index=True)
    base_url = fields.CharField(max_length=2048, null=True)
    api_key = fields.TextField()
    model = fields.CharField(max_length=255)
    timeout = fields.IntField(default=300)

    class Meta:
        table = "ai_providers"
        unique_together = (("name", "settings"),)


class AIProviderHeaders(TortoiseBase):
    id = fields.IntField(primary_key=True)
    provider = fields.ForeignKeyField(
        "models.AIProvider", related_name="request_headers", source_field="provider_id", on_delete=fields.NO_ACTION
    )
    key_name = fields.CharField(max_length=255, null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "ai_provider_headers"


class AIProviderParams(TortoiseBase):
    id = fields.IntField(primary_key=True)
    provider = fields.ForeignKeyField(
        "models.AIProvider", related_name="request_params", source_field="provider_id", on_delete=fields.NO_ACTION
    )
    key_name = fields.CharField(max_length=255, null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "ai_provider_params"


class GroupDataExportsModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="data_exports", source_field="group_id", null=True, on_delete=fields.NO_ACTION
    )
    name = fields.TextField()
    filename = fields.TextField()
    path = fields.TextField()
    size = fields.TextField()
    expires = fields.DatetimeField()

    class Meta:
        table = "group_data_exports"


class ReportModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    name = fields.TextField()
    status = fields.TextField()
    category = fields.CharField(max_length=255, db_index=True)
    timestamp = fields.DatetimeField(default=utc_now)
    group = fields.ForeignKeyField(
        "models.Group", related_name="group_reports", source_field="group_id", on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "group_reports"


class ReportEntryModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    success = fields.BooleanField(null=True, default=False)
    message = fields.TextField(null=True)
    exception = fields.TextField(null=True)
    timestamp = fields.DatetimeField(default=utc_now)
    report = fields.ForeignKeyField(
        "models.ReportModel", related_name="entries", source_field="report_id", on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "report_entries"


class GroupInviteToken(TortoiseBase):
    id = fields.IntField(primary_key=True)
    token = fields.CharField(max_length=255, unique=True)
    uses_left = fields.IntField(default=1)
    group = fields.ForeignKeyField(
        "models.Group", related_name="invite_tokens", source_field="group_id", null=True, on_delete=fields.NO_ACTION
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="invite_tokens",
        source_field="household_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "invite_tokens"


class CookBook(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    position = fields.IntField(default=1)
    group = fields.ForeignKeyField(
        "models.Group", related_name="cookbooks", source_field="group_id", null=True, on_delete=fields.NO_ACTION
    )
    household = fields.ForeignKeyField(
        "models.Household", related_name="cookbooks", source_field="household_id", null=True, on_delete=fields.NO_ACTION
    )
    name = fields.TextField()
    slug = fields.CharField(max_length=255, db_index=True)
    description = fields.TextField(null=True, default="")
    public = fields.BooleanField(null=True, default=False)
    query_filter_string = fields.TextField(default="")
    require_all_categories = fields.BooleanField(null=True, default=True)
    require_all_tags = fields.BooleanField(null=True, default=True)
    require_all_tools = fields.BooleanField(null=True, default=True)
    categories = fields.ManyToManyField(
        "models.Category",
        through="cookbooks_to_categories",
        forward_key="category_id",
        backward_key="cookbook_id",
        related_name="cookbooks",
        on_delete=fields.NO_ACTION,
    )
    tags = fields.ManyToManyField(
        "models.Tag",
        through="cookbooks_to_tags",
        forward_key="tag_id",
        backward_key="cookbook_id",
        related_name="cookbooks",
        on_delete=fields.NO_ACTION,
    )
    tools = fields.ManyToManyField(
        "models.Tool",
        through="cookbooks_to_tools",
        forward_key="tool_id",
        backward_key="cookbook_id",
        related_name="cookbooks",
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "cookbooks"
        unique_together = (("slug", "group"),)


class GroupMealPlanRules(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="meal_plan_rules", source_field="group_id", on_delete=fields.NO_ACTION
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="meal_plan_rules",
        source_field="household_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    day = fields.CharField(max_length=255, default="unset")
    entry_type = fields.CharField(max_length=255, default="")
    query_filter_string = fields.TextField(default="")
    categories = fields.ManyToManyField(
        "models.Category",
        through="plan_rules_to_categories",
        forward_key="category_id",
        backward_key="group_plan_rule_id",
        related_name="meal_plan_rules",
        on_delete=fields.NO_ACTION,
    )
    tags = fields.ManyToManyField(
        "models.Tag",
        through="plan_rules_to_tags",
        forward_key="tag_id",
        backward_key="plan_rule_id",
        related_name="meal_plan_rules",
        on_delete=fields.NO_ACTION,
    )
    households = fields.ManyToManyField(
        "models.Household",
        through="plan_rules_to_households",
        forward_key="household_id",
        backward_key="group_plan_rule_id",
        related_name="meal_plan_rules_with_household",
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "group_meal_plan_rules"


class GroupMealPlan(TortoiseBase):
    id = fields.IntField(primary_key=True)
    date = fields.DateField(db_index=True)
    entry_type = fields.CharField(max_length=255, db_index=True)
    title = fields.CharField(max_length=255, db_index=True)
    text = fields.TextField()
    group = fields.ForeignKeyField(
        "models.Group", related_name="mealplans", source_field="group_id", null=True, on_delete=fields.NO_ACTION
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="mealplans", source_field="user_id", null=True, on_delete=fields.NO_ACTION
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="meal_entries", source_field="recipe_id", null=True, on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "group_meal_plans"


class GroupRecipeAction(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="recipe_actions", source_field="group_id", on_delete=fields.NO_ACTION
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="recipe_actions",
        source_field="household_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    action_type = fields.CharField(max_length=255, db_index=True)
    title = fields.CharField(max_length=255, db_index=True)
    url = fields.TextField()

    class Meta:
        table = "recipe_actions"


class GroupWebhooksModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="webhooks", source_field="group_id", null=True, on_delete=fields.NO_ACTION
    )
    household = fields.ForeignKeyField(
        "models.Household", related_name="webhooks", source_field="household_id", null=True, on_delete=fields.NO_ACTION
    )
    enabled = fields.BooleanField(null=True, default=False)
    name = fields.TextField(null=True)
    url = fields.TextField(null=True)
    webhook_type = fields.TextField(null=True, default="")
    scheduled_time = fields.TimeField(null=True)
    time = fields.TextField(null=True, default="00:00")

    class Meta:
        table = "webhook_urls"


class GroupEventNotifierModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    name = fields.TextField()
    enabled = fields.BooleanField(default=True)
    apprise_url = fields.TextField()
    group = fields.ForeignKeyField(
        "models.Group",
        related_name="group_event_notifiers",
        source_field="group_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    household = fields.ForeignKeyField(
        "models.Household",
        related_name="group_event_notifiers",
        source_field="household_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "group_events_notifiers"


class GroupEventNotifierOptionsModel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    event_notifier = fields.ForeignKeyField(
        "models.GroupEventNotifierModel",
        related_name="options_rows",
        source_field="event_notifier_id",
        on_delete=fields.NO_ACTION,
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

    class Meta:
        table = "group_events_notifier_options"


class Category(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="owned_categories", source_field="group_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, db_index=True)

    class Meta:
        table = "categories"
        unique_together = (("slug", "group"),)


class Tag(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="tags", source_field="group_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, db_index=True)

    class Meta:
        table = "tags"
        unique_together = (("slug", "group"),)


class Tool(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="tools", source_field="group_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, db_index=True)
    on_hand = fields.BooleanField(null=True, default=False)

    class Meta:
        table = "tools"
        unique_together = (("slug", "group"),)


class ServerTaskModel(TortoiseBase):
    id = fields.IntField(primary_key=True)
    name = fields.TextField()
    completed_date = fields.DatetimeField(null=True)
    status = fields.TextField()
    log = fields.TextField(null=True)
    group = fields.ForeignKeyField(
        "models.Group", related_name="server_tasks", source_field="group_id", on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "server_tasks"


class ApiExtras(TortoiseBase):
    id = fields.IntField(primary_key=True)
    key_name = fields.CharField(max_length=255, null=True)
    value = fields.TextField(null=True)
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="extras", source_field="recipee_id", null=True, on_delete=fields.NO_ACTION
    )

    class Meta:
        table = "api_extras"


class IngredientFoodExtras(TortoiseBase):
    id = fields.IntField(primary_key=True)
    key_name = fields.CharField(max_length=255, null=True)
    value = fields.TextField(null=True)
    ingredient_food = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="extra_rows",
        source_field="ingredient_food_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "ingredient_food_extras"


class UserToRecipe(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    user = fields.ForeignKeyField(
        "models.User", related_name="recipe_ratings", source_field="user_id", on_delete=fields.NO_ACTION
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="user_ratings", source_field="recipe_id", on_delete=fields.NO_ACTION
    )
    rating = fields.FloatField(null=True, db_index=True)
    is_favorite = fields.BooleanField(db_index=True)

    class Meta:
        table = "users_to_recipes"
        unique_together = (("user", "recipe"), ("id", "user", "recipe"))


class HouseholdToRecipe(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    household = fields.ForeignKeyField(
        "models.Household", related_name="recipe_history", source_field="household_id", on_delete=fields.NO_ACTION
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe", related_name="household_history", source_field="recipe_id", on_delete=fields.NO_ACTION
    )
    last_made = fields.DatetimeField(null=True)

    class Meta:
        table = "households_to_recipes"
        unique_together = (("household", "recipe"), ("id", "household", "recipe"))


class ShoppingList(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    group = fields.ForeignKeyField(
        "models.Group", related_name="shopping_lists", source_field="group_id", on_delete=fields.NO_ACTION
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="shopping_lists", source_field="user_id", on_delete=fields.NO_ACTION
    )
    name = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "shopping_lists"


class ShoppingListItem(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="list_items",
        source_field="shopping_list_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    is_ingredient = fields.BooleanField(null=True, default=True)
    position = fields.IntField(default=0, db_index=True)
    checked = fields.BooleanField(null=True, default=False)
    quantity = fields.FloatField(null=True, default=1)
    note = fields.TextField(null=True)
    unit = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="shopping_list_items",
        source_field="unit_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    food = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="shopping_list_items",
        source_field="food_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    label = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_list_items",
        source_field="label_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    is_food = fields.BooleanField(null=True, default=False)

    class Meta:
        table = "shopping_list_items"


class ShoppingListExtras(TortoiseBase):
    id = fields.IntField(primary_key=True)
    key_name = fields.CharField(max_length=255, null=True)
    value = fields.TextField(null=True)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="extras",
        source_field="shopping_list_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "shopping_list_extras"


class ShoppingListItemExtras(TortoiseBase):
    id = fields.IntField(primary_key=True)
    key_name = fields.CharField(max_length=255, null=True)
    value = fields.TextField(null=True)
    shopping_list_item = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="extras",
        source_field="shopping_list_item_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )

    class Meta:
        table = "shopping_list_item_extras"


class ShoppingListRecipeReference(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="recipe_references",
        source_field="shopping_list_id",
        on_delete=fields.NO_ACTION,
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="shopping_list_refs",
        source_field="recipe_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    recipe_quantity = fields.FloatField()

    class Meta:
        table = "shopping_list_recipe_reference"
        unique_together = (("id", "shopping_list"),)
        unique_together = (("id", "shopping_list"),)


class ShoppingListItemRecipeReference(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    shopping_list_item = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="recipe_references",
        source_field="shopping_list_item_id",
        on_delete=fields.NO_ACTION,
    )
    recipe = fields.ForeignKeyField(
        "models.Recipe",
        related_name="shopping_list_item_refs",
        source_field="recipe_id",
        null=True,
        on_delete=fields.NO_ACTION,
    )
    recipe_quantity = fields.FloatField()
    recipe_scale = fields.FloatField(default=1)
    recipe_note = fields.TextField(null=True)

    class Meta:
        table = "shopping_list_item_recipe_reference"
        unique_together = (("id", "shopping_list_item"),)


class ShoppingListMultiPurposeLabel(TortoiseBase):
    id = GUIDField(max_length=32, primary_key=True, default=uuid4)
    shopping_list = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="label_settings",
        source_field="shopping_list_id",
        on_delete=fields.NO_ACTION,
    )
    label = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_list_settings",
        source_field="label_id",
        on_delete=fields.NO_ACTION,
    )
    position = fields.IntField(default=0)

    class Meta:
        table = "shopping_lists_multi_purpose_labels"
        unique_together = (("shopping_list", "label"), ("id", "shopping_list", "label"))
