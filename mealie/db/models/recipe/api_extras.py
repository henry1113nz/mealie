from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel

if TYPE_CHECKING:
    from mealie.db.models.household.shopping_list import ShoppingList, ShoppingListItem
    from mealie.db.models.recipe.ingredient import IngredientFoodModel
    from mealie.db.models.recipe.recipe import RecipeModel


class ApiExtras(TortoiseModel):
    __tablename__ = "api_extras"
    __filterable_fields__ = {"id", "key_name", "recipee_id", "value"}
    __association_proxies__ = {"recipee_id": ["recipe_id"]}

    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="extras",
        source_field="recipee_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)

    @property
    def recipee_id(self) -> UUID | None:
        return self.recipe_id

    @recipee_id.setter
    def recipee_id(self, value: UUID | None) -> None:
        self.recipe_id = value

    class Meta:
        table = "api_extras"


class IngredientFoodExtras(TortoiseModel):
    __tablename__ = "ingredient_food_extras"
    __filterable_fields__ = {"value", "key_name", "id", "ingredient_food_id"}
    __association_proxies__ = {}

    ingredient_food_id: UUID | None
    ingredient_food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="extras",
        source_field="ingredient_food_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "ingredient_food_extras"


class ShoppingListExtras(TortoiseModel):
    __tablename__ = "shopping_list_extras"
    __filterable_fields__ = {"shopping_list_id", "key_name", "id", "value"}
    __association_proxies__ = {}

    shopping_list_id: UUID | None
    shopping_list: fields.ForeignKeyNullableRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="extras",
        source_field="shopping_list_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "shopping_list_extras"


class ShoppingListItemExtras(TortoiseModel):
    __tablename__ = "shopping_list_item_extras"
    __filterable_fields__ = {"shopping_list_item_id", "value", "key_name", "id"}
    __association_proxies__ = {}

    shopping_list_item_id: UUID | None
    shopping_list_item: fields.ForeignKeyNullableRelation[ShoppingListItem] = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="extras",
        source_field="shopping_list_item_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    id = fields.IntField(primary_key=True)
    key_name = fields.TextField(null=True)
    value = fields.TextField(null=True)

    class Meta:
        table = "shopping_list_item_extras"
