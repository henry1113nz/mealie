from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from tortoise import fields

from mealie.db.models._model_base import TortoiseModel
from mealie.db.models.recipe.api_extras import ShoppingListExtras as ShoppingListExtras

if TYPE_CHECKING:
    from mealie.db.models.group.group import Group
    from mealie.db.models.recipe.ingredient import IngredientFoodModel, IngredientUnitModel
    from mealie.db.models.recipe.labels import MultiPurposeLabel
    from mealie.db.models.recipe.recipe import RecipeModel
    from mealie.db.models.users.users import User


class ShoppingListItemRecipeReference(TortoiseModel):
    __tablename__ = "shopping_list_item_recipe_reference"
    __filterable_fields__ = {
        "recipe_note",
        "id",
        "shopping_list_item_id",
        "recipe_quantity",
        "recipe_scale",
        "recipe_id",
    }
    __association_proxies__ = {
        "group_id": ["shopping_list_item", "group_id"],
        "household_id": ["shopping_list_item", "household_id"],
    }

    id = fields.UUIDField(primary_key=True, default=uuid4)
    shopping_list_item_id: UUID
    shopping_list_item: fields.ForeignKeyRelation[ShoppingListItem] = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="recipe_references",
        source_field="shopping_list_item_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="shopping_list_item_refs",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    recipe_quantity = fields.FloatField(null=False)
    recipe_scale = fields.FloatField(null=False, default=1)
    recipe_note = fields.TextField(null=True)

    @property
    def group_id(self):
        parent = getattr(self, "shopping_list_item", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "shopping_list_item", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "shopping_list_item_recipe_reference"


class ShoppingListItem(TortoiseModel):
    __tablename__ = "shopping_list_items"
    __filterable_fields__ = {
        "quantity",
        "checked",
        "unit_id",
        "food_id",
        "position",
        "label_id",
        "id",
        "note",
        "is_ingredient",
        "shopping_list_id",
    }
    __association_proxies__ = {
        "group_id": ["shopping_list", "group_id"],
        "household_id": ["shopping_list", "household_id"],
    }
    model_config = {"exclude": {"label", "food", "unit"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    shopping_list_id: UUID | None
    shopping_list: fields.ForeignKeyNullableRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="list_items",
        source_field="shopping_list_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    is_ingredient = fields.BooleanField(null=True, default=True)
    position = fields.IntField(null=False, db_index=True, default=0)
    checked = fields.BooleanField(null=True, default=False)
    quantity = fields.FloatField(null=True, default=1)
    note = fields.TextField(null=True)
    unit_id: UUID | None
    unit: fields.ForeignKeyNullableRelation[IngredientUnitModel] = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="shopping_list_items_unit",
        source_field="unit_id",
        null=True,
        on_delete=fields.SET_NULL,
    )
    food_id: UUID | None
    food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="shopping_list_items_food",
        source_field="food_id",
        null=True,
        on_delete=fields.SET_NULL,
    )
    label_id: UUID | None
    label: fields.ForeignKeyNullableRelation[MultiPurposeLabel] = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_list_items",
        source_field="label_id",
        null=True,
        on_delete=fields.SET_NULL,
    )
    is_food = fields.BooleanField(null=True, default=False)

    @property
    def group_id(self):
        parent = getattr(self, "shopping_list", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "shopping_list", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "shopping_list_items"
        ordering = ("position", "id")


class ShoppingListRecipeReference(TortoiseModel):
    __tablename__ = "shopping_list_recipe_reference"
    __filterable_fields__ = {"shopping_list_id", "id", "recipe_id", "recipe_quantity"}
    __association_proxies__ = {
        "group_id": ["shopping_list", "group_id"],
        "household_id": ["shopping_list", "household_id"],
    }
    model_config = {"exclude": {"id", "recipe"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    shopping_list_id: UUID
    shopping_list: fields.ForeignKeyRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="recipe_references",
        source_field="shopping_list_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="shopping_list_refs",
        source_field="recipe_id",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    recipe_quantity = fields.FloatField(null=False)

    @property
    def group_id(self):
        parent = getattr(self, "shopping_list", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "shopping_list", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "shopping_list_recipe_reference"


class ShoppingListMultiPurposeLabel(TortoiseModel):
    __tablename__ = "shopping_lists_multi_purpose_labels"
    __filterable_fields__ = {"label_id", "shopping_list_id", "position", "id"}
    __association_proxies__ = {
        "group_id": ["shopping_list", "group_id"],
        "household_id": ["shopping_list", "household_id"],
    }
    model_config = {"exclude": {"label"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    shopping_list_id: UUID
    shopping_list: fields.ForeignKeyRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="label_settings",
        source_field="shopping_list_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    label_id: UUID
    label: fields.ForeignKeyRelation[MultiPurposeLabel] = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_lists_label_settings",
        source_field="label_id",
        null=False,
        on_delete=fields.CASCADE,
    )
    position = fields.IntField(null=False, default=0)

    @property
    def group_id(self):
        parent = getattr(self, "shopping_list", None)
        return getattr(parent, "group_id", None) if parent is not None else None

    @property
    def household_id(self):
        parent = getattr(self, "shopping_list", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    class Meta:
        table = "shopping_lists_multi_purpose_labels"
        unique_together = (("shopping_list_id", "label_id"),)
        ordering = ("position", "id")


class ShoppingList(TortoiseModel):
    __tablename__ = "shopping_lists"
    __filterable_fields__ = {"name", "group_id", "id", "user_id"}
    __association_proxies__ = {"household_id": ["user", "household_id"], "household": ["user", "household"]}
    model_config = {"exclude": {"id", "list_items"}}

    id = fields.UUIDField(primary_key=True, default=uuid4)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="shopping_lists",
        source_field="group_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="shopping_lists",
        source_field="user_id",
        null=False,
        on_delete=fields.CASCADE,
        db_index=True,
    )
    name = fields.TextField(null=True)
    label_settings: fields.ReverseRelation[ShoppingListMultiPurposeLabel]

    @property
    def household_id(self):
        parent = getattr(self, "user", None)
        return getattr(parent, "household_id", None) if parent is not None else None

    @property
    def household(self):
        parent = getattr(self, "user", None)
        return getattr(parent, "household", None) if parent is not None else None

    class Meta:
        table = "shopping_lists"
