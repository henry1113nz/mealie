from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.recipe.labels import MultiPurposeLabel
    from mealie.db.models.recipe.recipe import RecipeModel


class IngredientUnitModel(TortoiseModel):
    __tablename__ = "ingredient_units"
    __filterable_fields__ = {
        "abbreviation",
        "name",
        "fraction",
        "abbreviation_normalized",
        "name_normalized",
        "id",
        "standard_unit",
        "plural_name_normalized",
        "plural_abbreviation_normalized",
        "plural_name",
        "use_abbreviation",
        "standard_quantity",
        "plural_abbreviation",
        "group_id",
        "description",
    }
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="ingredient_units",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = fields.TextField(null=True)
    plural_name = fields.TextField(null=True)
    description = fields.TextField(null=True)
    abbreviation = fields.TextField(null=True)
    plural_abbreviation = fields.TextField(null=True)
    use_abbreviation = fields.BooleanField(null=True, default=False)
    fraction = fields.BooleanField(null=True, default=True)
    standard_quantity = fields.FloatField(null=True)
    standard_unit = fields.TextField(null=True)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    abbreviation_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_abbreviation_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_units"
        unique_together = (("name", "group_id"),)


class IngredientFoodModel(TortoiseModel):
    __tablename__ = "ingredient_foods"
    __filterable_fields__ = {
        "label_id",
        "name",
        "name_normalized",
        "id",
        "plural_name_normalized",
        "plural_name",
        "group_id",
        "description",
    }
    __association_proxies__ = {}
    model_config = {"exclude": {"households_with_ingredient_food", "substitutions"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="ingredient_foods",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = fields.TextField(null=True)
    plural_name = fields.TextField(null=True)
    description = fields.TextField(null=True)
    label_id: UUID | None
    label: fields.ForeignKeyNullableRelation[MultiPurposeLabel] = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="foods",
        source_field="label_id",
        null=True,
        on_delete=fields.SET_NULL,
        db_index=True,
    )
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    plural_name_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    on_hand = fields.BooleanField(null=False, default=False)
    households_with_ingredient_food = fields.ManyToManyField(
        "models.Household",
        related_name="ingredient_foods_on_hand",
        through="households_to_ingredient_foods",
        backward_key="food_id",
        forward_key="household_id",
    )

    class Meta:
        table = "ingredient_foods"
        unique_together = (("name", "group_id"),)


class IngredientUnitAliasModel(TortoiseModel):
    __tablename__ = "ingredient_units_aliases"
    __filterable_fields__ = {"unit_id", "name_normalized", "id", "name"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    unit_id: UUID
    unit: fields.ForeignKeyRelation[IngredientUnitModel] = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="aliases",
        source_field="unit_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    name = fields.TextField(null=False)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_units_aliases"


class IngredientFoodAliasModel(TortoiseModel):
    __tablename__ = "ingredient_foods_aliases"
    __filterable_fields__ = {"food_id", "name_normalized", "id", "name"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    food_id: UUID
    food: fields.ForeignKeyRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="aliases",
        source_field="food_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    name = fields.TextField(null=False)
    name_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_aliases"


class IngredientFoodSubstitutionModel(TortoiseModel):
    __tablename__ = "ingredient_foods_substitutions"
    __filterable_fields__ = {"food_id", "position", "id", "substitute_food_id", "note"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    food_id: UUID
    food: fields.ForeignKeyRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="substitutions",
        source_field="food_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    substitute_food_id: UUID | None
    substitute_food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="substitution_references",
        source_field="substitute_food_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    note = fields.TextField(null=True)
    position = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "ingredient_foods_substitutions"
        unique_together = (("food_id", "substitute_food_id"),)
        ordering = ("position", "id")


class RecipeIngredientModel(TortoiseModel):
    __tablename__ = "recipes_ingredients"
    __filterable_fields__ = {
        "quantity",
        "unit_id",
        "food_id",
        "position",
        "referenced_recipe_id",
        "reference_id",
        "note_normalized",
        "title",
        "id",
        "original_text_normalized",
        "note",
        "recipe_id",
        "original_text",
    }
    __association_proxies__ = {}
    model_config = {"exclude": {"id", "substitutions"}}

    id = fields.IntField(primary_key=True)
    position = fields.IntField(null=True, db_index=True)
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="recipe_ingredient",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
    )
    title = fields.TextField(null=True)
    note = fields.TextField(null=True)
    unit_id: UUID | None
    unit: fields.ForeignKeyNullableRelation[IngredientUnitModel] = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="ingredients",
        source_field="unit_id",
        null=True,
        on_delete=fields.SET_NULL,
        db_index=True,
    )
    food_id: UUID | None
    food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="ingredients",
        source_field="food_id",
        null=True,
        on_delete=fields.SET_NULL,
        db_index=True,
    )
    quantity = fields.FloatField(null=True)
    original_text = fields.TextField(null=True)
    reference_id = fields.UUIDField(null=True)
    referenced_recipe_id: UUID | None
    referenced_recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="referenced_ingredients",
        source_field="referenced_recipe_id",
        null=True,
        on_delete=fields.SET_NULL,
        db_index=True,
    )
    note_normalized = fields.CharField(max_length=255, null=True, db_index=True)
    original_text_normalized = fields.CharField(max_length=255, null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients"
        ordering = ("position", "id")


class RecipeIngredientSubstitutionModel(TortoiseModel):
    __tablename__ = "recipes_ingredients_substitutions"
    __filterable_fields__ = {"position", "id", "substitute_food_id", "note", "ingredient_id"}
    __association_proxies__ = {}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    ingredient_id: int
    ingredient: fields.ForeignKeyRelation[RecipeIngredientModel] = fields.ForeignKeyField(
        "models.RecipeIngredientModel",
        related_name="substitutions",
        source_field="ingredient_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    substitute_food_id: UUID | None
    substitute_food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="recipe_substitution_references",
        source_field="substitute_food_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    note = fields.TextField(null=True)
    position = fields.IntField(null=True, db_index=True)

    class Meta:
        table = "recipes_ingredients_substitutions"
        ordering = ("position", "id")


async def resolve_substitutions(
    using_db,
    group_id,
    substitutions: list[dict] | None,
    exclude_food_id=None,
) -> list[tuple]:
    """Resolve substitute foods inside the owning group, preserving note-only rows."""
    if not substitutions or not group_id:
        return []
    requested = {str(row["substitute_food_id"]) for row in substitutions if row.get("substitute_food_id")}
    resolvable = (
        {
            str(pk)
            for pk in await IngredientFoodModel.filter(group_id=group_id, id__in=requested)
            .using_db(using_db)
            .values_list("id", flat=True)
        }
        if requested
        else set()
    )
    result = []
    seen: set[str] = set()
    for row in substitutions:
        food_id = row.get("substitute_food_id")
        note = (row.get("note") or "").strip() or None
        if food_id:
            key = str(food_id)
            if key not in resolvable or key == str(exclude_food_id) or key in seen:
                continue
            seen.add(key)
        elif not note:
            continue
        result.append((food_id, note))
    return result
