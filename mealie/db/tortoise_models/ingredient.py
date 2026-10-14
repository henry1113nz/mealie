from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

from ._base import TortoiseBaseModel


class IngredientUnit(TortoiseBaseModel):
    group: fields.ForeignKeyRelation["Group"] = fields.ForeignKeyField(
        "models.Group", related_name="ingredient_units", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    name = fields.CharField(max_length=255, null=True)
    plural_name = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    abbreviation = fields.CharField(max_length=255, null=True)
    plural_abbreviation = fields.CharField(max_length=255, null=True)
    use_abbreviation = fields.BooleanField(default=False, null=True)
    fraction = fields.BooleanField(default=True, null=True)
    standard_quantity = fields.FloatField(null=True)
    standard_unit = fields.CharField(max_length=255, null=True)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    abbreviation_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_abbreviation_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_units"
        unique_together = (("name", "group"),)


class IngredientFood(TortoiseBaseModel):
    group: fields.ForeignKeyRelation["Group"] = fields.ForeignKeyField(
        "models.Group", related_name="ingredient_foods", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    name = fields.CharField(max_length=255, null=True)
    plural_name = fields.CharField(max_length=255, null=True)
    description = fields.TextField(null=True)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    on_hand = fields.BooleanField(default=False)

    class Meta:
        table = "ingredient_foods"
        unique_together = (("name", "group"),)


class _IngredientAliasBase(Model):
    """Give Tortoise a row key while retaining each alias's legacy UUID id."""

    row_id = fields.IntField(primary_key=True)
    id = fields.UUIDField(default=uuid4)
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class IngredientUnitAlias(_IngredientAliasBase):
    unit: fields.ForeignKeyRelation[IngredientUnit] = fields.ForeignKeyField(
        "models.IngredientUnit", related_name="aliases", on_delete=fields.OnDelete.NO_ACTION
    )
    name = fields.CharField(max_length=255)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_units_aliases"
        unique_together = (("id", "unit"),)


class IngredientFoodAlias(_IngredientAliasBase):
    food: fields.ForeignKeyRelation[IngredientFood] = fields.ForeignKeyField(
        "models.IngredientFood", related_name="aliases", on_delete=fields.OnDelete.NO_ACTION
    )
    name = fields.CharField(max_length=255)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_aliases"
        unique_together = (("id", "food"),)


class IngredientFoodSubstitution(TortoiseBaseModel):
    food: fields.ForeignKeyRelation[IngredientFood] = fields.ForeignKeyField(
        "models.IngredientFood", related_name="substitutions", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    substitute_food: fields.ForeignKeyNullableRelation[IngredientFood] = fields.ForeignKeyField(
        "models.IngredientFood", related_name="substitution_references", null=True,
        on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    note = fields.TextField(null=True)
    position = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_substitutions"
        unique_together = (("food", "substitute_food"),)


class RecipeIngredient(Model):
    id = fields.IntField(primary_key=True)
    position = fields.IntField(null=True, db_index=True)
    recipe: fields.ForeignKeyNullableRelation["Recipe"] = fields.ForeignKeyField(
        "models.Recipe", related_name="ingredients", null=True, on_delete=fields.OnDelete.NO_ACTION
    )
    title = fields.CharField(max_length=255, null=True)
    note = fields.TextField(null=True)
    unit: fields.ForeignKeyNullableRelation[IngredientUnit] = fields.ForeignKeyField(
        "models.IngredientUnit", related_name="ingredients", null=True, on_delete=fields.OnDelete.NO_ACTION,
        db_index=True
    )
    food: fields.ForeignKeyNullableRelation[IngredientFood] = fields.ForeignKeyField(
        "models.IngredientFood", related_name="ingredients", null=True, on_delete=fields.OnDelete.NO_ACTION,
        db_index=True
    )
    quantity = fields.FloatField(null=True)
    original_text = fields.TextField(null=True)
    reference_id = fields.UUIDField(null=True)
    referenced_recipe: fields.ForeignKeyNullableRelation["Recipe"] = fields.ForeignKeyField(
        "models.Recipe", related_name="referenced_ingredients", null=True, on_delete=fields.OnDelete.NO_ACTION,
        db_index=True
    )
    note_normalized = fields.CharField(max_length=2048, null=True, db_index=True)
    original_text_normalized = fields.CharField(max_length=2048, null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients"
        ordering = ["position"]


class RecipeIngredientSubstitution(TortoiseBaseModel):
    ingredient: fields.ForeignKeyRelation[RecipeIngredient] = fields.ForeignKeyField(
        "models.RecipeIngredient", related_name="substitutions", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    substitute_food: fields.ForeignKeyNullableRelation[IngredientFood] = fields.ForeignKeyField(
        "models.IngredientFood", related_name="recipe_substitution_references", null=True,
        on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )
    note = fields.TextField(null=True)
    position = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients_substitutions"


class HouseholdIngredientFood(Model):
    """The existing association table, registered for schema/constraint fidelity."""

    household: fields.ForeignKeyRelation["Household"] = fields.ForeignKeyField(
        "models.Household", related_name="ingredient_food_links", on_delete=fields.OnDelete.NO_ACTION
    )
    food: fields.ForeignKeyRelation[IngredientFood] = fields.ForeignKeyField(
        "models.IngredientFood", related_name="household_links", on_delete=fields.OnDelete.NO_ACTION
    )

    class Meta:
        table = "households_to_ingredient_foods"
        unique_together = (("household", "food"),)
