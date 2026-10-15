"""Tortoise mappings for the full legacy table graph.

The mappings preserve legacy table and column names. Tortoise's field metadata
cannot represent every legacy primary key or database-only constraint; those
inventory differences and required migration operations are recorded in
``STAGE5_MODEL_INVENTORY.md``.
"""

from . import remaining as _remaining
from .group import Group
from .household import Household
from .ingredient import (
    HouseholdIngredientFood,
    IngredientFood,
    IngredientFoodAlias,
    IngredientFoodSubstitution,
    IngredientUnit,
    IngredientUnitAlias,
    RecipeIngredient,
    RecipeIngredientSubstitution,
)
from .recipe import Recipe, RecipeNutrition
from .remaining import *
from .user import AuthMethod, User

__all__ = [
    "AuthMethod",
    "Group",
    "Household",
    "IngredientFood",
    "IngredientFoodAlias",
    "IngredientFoodSubstitution",
    "HouseholdIngredientFood",
    "IngredientUnit",
    "IngredientUnitAlias",
    "Recipe",
    "RecipeIngredient",
    "RecipeIngredientSubstitution",
    "RecipeNutrition",
    "User",
    *_remaining.__all__,
]
