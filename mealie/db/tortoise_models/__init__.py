"""Incremental Tortoise model graph.

These mappings coexist with the legacy SQLAlchemy models during the staged
migration. This registry currently covers groups, households, users, recipe
core, ingredients, foods and units. It keeps legacy table and column names and
mirrors the constraints represented by these mappings:

* ``groups.name`` and ``groups.slug`` are unique (and indexed).
* Household names and slugs are unique within a group; both are indexed.
* User usernames and emails are globally unique and indexed.
* Recipe slugs are unique within a group.
* Food and unit names are unique within a group.

The substitution CHECK constraints and PostgreSQL trigram indexes require
custom migration DDL; Tortoise model metadata cannot represent them.

The SQLite mappings use Tortoise UUID fields and are also compatible with
PostgreSQL UUID columns. PostgreSQL schema creation and constraint behavior
still requires a separate backend smoke check.
"""

from .group import Group
from .household import Household
from .ingredient import (
    IngredientFood,
    IngredientFoodAlias,
    IngredientFoodSubstitution,
    IngredientUnit,
    IngredientUnitAlias,
    RecipeIngredient,
    RecipeIngredientSubstitution,
)
from .recipe import Recipe, RecipeNutrition
from .user import AuthMethod, User

__all__ = [
    "AuthMethod",
    "Group",
    "Household",
    "IngredientFood",
    "IngredientFoodAlias",
    "IngredientFoodSubstitution",
    "IngredientUnit",
    "IngredientUnitAlias",
    "Recipe",
    "RecipeIngredient",
    "RecipeIngredientSubstitution",
    "RecipeNutrition",
    "User",
]
