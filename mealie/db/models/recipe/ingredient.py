from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._tortoise_base import UnboundedCharField, UUIDField

from ._base import RecipeBase

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.household.household import Household
    from mealie.db.models.recipe.api_extras import IngredientFoodExtras
    from mealie.db.models.recipe.labels import MultiPurposeLabel
    from mealie.db.models.recipe.recipe import RecipeModel


class IngredientFoodAliasModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    food_id: UUID
    food: fields.ForeignKeyRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="aliases",
        source_field="food_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str] = UnboundedCharField()
    name_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_aliases"
        unique_together = (("id", "food"),)


class IngredientFoodModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="ingredient_foods",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str | None] = UnboundedCharField(null=True)
    plural_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    description: fields.TextField[str | None] = UnboundedCharField(null=True)
    label_id: UUID | None
    label: fields.ForeignKeyNullableRelation[MultiPurposeLabel] = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="foods",
        source_field="label_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    plural_name_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    on_hand: fields.BooleanField[bool] = fields.BooleanField(default=False)
    substitutions: fields.ReverseRelation[IngredientFoodSubstitutionModel]
    substitution_references: fields.ReverseRelation[IngredientFoodSubstitutionModel]
    extras: fields.ReverseRelation[IngredientFoodExtras]
    ingredients: fields.ReverseRelation[RecipeIngredientModel]
    recipe_substitution_references: fields.ReverseRelation[RecipeIngredientSubstitutionModel]
    aliases: fields.ReverseRelation[IngredientFoodAliasModel]
    households_with_ingredient_food: fields.ManyToManyRelation[Household] = fields.ManyToManyField(
        "models.Household",
        related_name="ingredient_foods_on_hand",
        through="households_to_ingredient_foods",
        backward_key="food_id",
        forward_key="household_id",
        on_delete=fields.RESTRICT,
    )

    class Meta:
        table = "ingredient_foods"
        unique_together = (("name", "group"),)


class IngredientFoodSubstitutionModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    food_id: UUID
    food: fields.ForeignKeyRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="substitutions",
        source_field="food_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    substitute_food_id: UUID | None
    substitute_food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="substitution_references",
        source_field="substitute_food_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    note: fields.TextField[str | None] = UnboundedCharField(null=True)
    position: fields.IntField[int | None] = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_substitutions"
        unique_together = (("food", "substitute_food"),)
        ordering = ("position",)


class IngredientUnitAliasModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    unit_id: UUID
    unit: fields.ForeignKeyRelation[IngredientUnitModel] = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="aliases",
        source_field="unit_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str] = UnboundedCharField()
    name_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)

    class Meta:
        table = "ingredient_units_aliases"
        unique_together = (("id", "unit"),)


class IngredientUnitModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="ingredient_units",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str | None] = UnboundedCharField(null=True)
    plural_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    description: fields.TextField[str | None] = UnboundedCharField(null=True)
    abbreviation: fields.TextField[str | None] = UnboundedCharField(null=True)
    plural_abbreviation: fields.TextField[str | None] = UnboundedCharField(null=True)
    use_abbreviation: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=False)
    fraction: fields.BooleanField[bool | None] = fields.BooleanField(null=True, default=True)
    standard_quantity: fields.FloatField[float | None] = fields.FloatField(null=True)
    standard_unit: fields.TextField[str | None] = UnboundedCharField(null=True)
    name_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    plural_name_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    abbreviation_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    plural_abbreviation_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    ingredients: fields.ReverseRelation[RecipeIngredientModel]
    aliases: fields.ReverseRelation[IngredientUnitAliasModel]

    class Meta:
        table = "ingredient_units"
        unique_together = (("name", "group"),)


class RecipeIngredientModel(RecipeBase):
    position: fields.IntField[int | None] = fields.IntField(null=True, db_index=True)
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="recipe_ingredient",
        source_field="recipe_id",
        null=True,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    title: fields.TextField[str | None] = UnboundedCharField(null=True)
    note: fields.TextField[str | None] = UnboundedCharField(null=True)
    unit_id: UUID | None
    unit: fields.ForeignKeyNullableRelation[IngredientUnitModel] = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="ingredients",
        source_field="unit_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    food_id: UUID | None
    food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="ingredients",
        source_field="food_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    quantity: fields.FloatField[float | None] = fields.FloatField(null=True)
    original_text: fields.TextField[str | None] = UnboundedCharField(null=True)
    reference_id: fields.UUIDField[UUID | None] = UUIDField(null=True)
    referenced_recipe_id: UUID | None
    referenced_recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="referenced_ingredients",
        source_field="referenced_recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    note_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    original_text_normalized: fields.TextField[str | None] = UnboundedCharField(null=True, db_index=True)
    substitutions: fields.ReverseRelation[RecipeIngredientSubstitutionModel]

    class Meta:
        table = "recipes_ingredients"
        ordering = ("position",)


class RecipeIngredientSubstitutionModel(RecipeBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    ingredient_id: int
    ingredient: fields.ForeignKeyRelation[RecipeIngredientModel] = fields.ForeignKeyField(
        "models.RecipeIngredientModel",
        related_name="substitutions",
        source_field="ingredient_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    substitute_food_id: UUID | None
    substitute_food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="recipe_substitution_references",
        source_field="substitute_food_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    note: fields.TextField[str | None] = UnboundedCharField(null=True)
    position: fields.IntField[int | None] = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients_substitutions"
        ordering = ("position",)
