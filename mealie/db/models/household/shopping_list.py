from typing import TYPE_CHECKING
from uuid import UUID

from tortoise import fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import TortoiseBase, UnboundedCharField, UUIDField

if TYPE_CHECKING:
    from ..group.group import Group
    from ..recipe.ingredient import IngredientFoodModel, IngredientUnitModel
    from ..recipe.labels import MultiPurposeLabel
    from ..recipe.recipe import RecipeModel
    from ..users.users import User


class ShoppingList(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    group_id: UUID
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group",
        related_name="shopping_lists",
        source_field="group_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    user_id: UUID
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="shopping_lists",
        source_field="user_id",
        null=False,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    name: fields.TextField[str | None] = UnboundedCharField(null=True)
    list_items: fields.ReverseRelation[ShoppingListItem]
    recipe_references: fields.ReverseRelation[ShoppingListRecipeReference]
    label_settings: fields.ReverseRelation[ShoppingListMultiPurposeLabel]
    extras: fields.ReverseRelation[ShoppingListExtras]

    class Meta:
        table = "shopping_lists"

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._household_coexistence import delete_shopping_list_dependents

        if using_db is not None:
            await delete_shopping_list_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_shopping_list_dependents(self.id, connection)
                await super().delete(using_db=connection)


class ShoppingListItem(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    shopping_list_id: UUID | None
    shopping_list: fields.ForeignKeyNullableRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="list_items",
        source_field="shopping_list_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    is_ingredient: fields.BooleanField[bool | None] = fields.BooleanField(default=True, null=True)
    position = fields.IntField(default=0, db_index=True)
    checked: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    quantity: fields.FloatField[float | None] = fields.FloatField(default=1, null=True)
    note: fields.TextField[str | None] = UnboundedCharField(null=True)
    unit_id: UUID | None
    unit: fields.ForeignKeyNullableRelation[IngredientUnitModel] = fields.ForeignKeyField(
        "models.IngredientUnitModel",
        related_name="shopping_list_items",
        source_field="unit_id",
        null=True,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    food_id: UUID | None
    food: fields.ForeignKeyNullableRelation[IngredientFoodModel] = fields.ForeignKeyField(
        "models.IngredientFoodModel",
        related_name="shopping_list_items",
        source_field="food_id",
        null=True,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    label_id: UUID | None
    label: fields.ForeignKeyNullableRelation[MultiPurposeLabel] = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_list_items",
        source_field="label_id",
        null=True,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    is_food: fields.BooleanField[bool | None] = fields.BooleanField(default=False, null=True)
    recipe_references: fields.ReverseRelation[ShoppingListItemRecipeReference]
    extras: fields.ReverseRelation[ShoppingListItemExtras]

    class Meta:
        table = "shopping_list_items"

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._household_coexistence import delete_shopping_list_item_dependents

        if using_db is not None:
            await delete_shopping_list_item_dependents(self.id, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_shopping_list_item_dependents(self.id, connection)
                await super().delete(using_db=connection)


class ShoppingListRecipeReference(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    shopping_list_id: UUID
    shopping_list: fields.ForeignKeyRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="recipe_references",
        source_field="shopping_list_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="shopping_list_refs",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    recipe_quantity = fields.FloatField()

    class Meta:
        table = "shopping_list_recipe_reference"


class ShoppingListItemRecipeReference(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    shopping_list_item_id: UUID
    shopping_list_item: fields.ForeignKeyRelation[ShoppingListItem] = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="recipe_references",
        source_field="shopping_list_item_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    recipe_id: UUID | None
    recipe: fields.ForeignKeyNullableRelation[RecipeModel] = fields.ForeignKeyField(
        "models.RecipeModel",
        related_name="shopping_list_item_refs",
        source_field="recipe_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    recipe_quantity = fields.FloatField()
    recipe_scale = fields.FloatField(default=1)
    recipe_note: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "shopping_list_item_recipe_reference"


class ShoppingListMultiPurposeLabel(TortoiseBase):
    id: fields.UUIDField[UUID] = UUIDField(primary_key=True)
    shopping_list_id: UUID
    shopping_list: fields.ForeignKeyRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="label_settings",
        source_field="shopping_list_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    label_id: UUID
    label: fields.ForeignKeyRelation[MultiPurposeLabel] = fields.ForeignKeyField(
        "models.MultiPurposeLabel",
        related_name="shopping_lists_label_settings",
        source_field="label_id",
        null=False,
        db_index=False,
        on_delete=fields.RESTRICT,
    )
    position = fields.IntField(default=0)

    class Meta:
        table = "shopping_lists_multi_purpose_labels"
        unique_together = (("shopping_list", "label_id"),)


class ShoppingListExtras(TortoiseBase):
    shopping_list_id: UUID | None
    shopping_list: fields.ForeignKeyNullableRelation[ShoppingList] = fields.ForeignKeyField(
        "models.ShoppingList",
        related_name="extras",
        source_field="shopping_list_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    key_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    value: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "shopping_list_extras"


class ShoppingListItemExtras(TortoiseBase):
    shopping_list_item_id: UUID | None
    shopping_list_item: fields.ForeignKeyNullableRelation[ShoppingListItem] = fields.ForeignKeyField(
        "models.ShoppingListItem",
        related_name="extras",
        source_field="shopping_list_item_id",
        null=True,
        db_index=True,
        on_delete=fields.RESTRICT,
    )
    key_name: fields.TextField[str | None] = UnboundedCharField(null=True)
    value: fields.TextField[str | None] = UnboundedCharField(null=True)

    class Meta:
        table = "shopping_list_item_extras"
