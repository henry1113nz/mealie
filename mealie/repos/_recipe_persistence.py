"""Native recipe hydration and transactional nested-row replacement."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from tortoise import Model

from mealie.db.models.recipe.api_extras import ApiExtras
from mealie.db.models.recipe.assets import RecipeAsset
from mealie.db.models.recipe.comment import RecipeComment
from mealie.db.models.recipe.ingredient import (
    IngredientFoodModel,
    IngredientUnitModel,
    RecipeIngredientModel,
    RecipeIngredientSubstitutionModel,
)
from mealie.db.models.recipe.instruction import RecipeIngredientRefLink, RecipeInstruction, RecipeNoteRefLink
from mealie.db.models.recipe.note import Note
from mealie.db.models.recipe.nutrition import Nutrition
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.settings import RecipeSettings
from mealie.db.models.users import User

from .repository_recipe_base import hydrate_recipe_entity, model_data, resolve_substitutions


async def recipe_data(
    entry: RecipeModel, summary: bool = False, *, _visited: frozenset[UUID] = frozenset()
) -> dict[str, Any]:
    """Materialize responses before leaving the owning database event loop.

    Referenced recipes can form cycles; at a repeated recipe, return its summary
    and let unchanged schema defaults terminate the nested representation.
    """
    data = model_data(entry)
    user = await User.get_or_none(id=entry.user_id) if entry.user_id else None
    data["household_id"] = user.household_id if user else None
    for field in ("recipe_category", "tags", "tools"):
        data[field] = [await hydrate_recipe_entity(item) for item in await getattr(entry, field).all()]
    if summary or entry.id in _visited:
        return data
    visited = _visited | {entry.id}
    data["assets"] = await RecipeAsset.filter(recipe_id=entry.id).values()
    data["notes"] = await Note.filter(recipe_id=entry.id).order_by("id").values()
    data["extras"] = {row.key_name: row.value for row in await ApiExtras.filter(recipee_id=entry.id)}
    nutrition = await Nutrition.filter(recipe_id=entry.id).first()
    settings = await RecipeSettings.filter(recipe_id=entry.id).first()
    data["nutrition"] = model_data(nutrition) if nutrition else None
    data["settings"] = model_data(settings) if settings else None
    data["comments"] = [
        await hydrate_recipe_entity(comment) for comment in await RecipeComment.filter(recipe_id=entry.id)
    ]
    data["recipe_ingredient"] = []
    for ingredient in await RecipeIngredientModel.filter(recipe_id=entry.id).order_by("position"):
        item = model_data(ingredient)
        for field, model in (("food", IngredientFoodModel), ("unit", IngredientUnitModel)):
            identifier = getattr(ingredient, field + "_id")
            related = await model.get_or_none(id=identifier) if identifier else None
            item[field] = await hydrate_recipe_entity(related) if related else None
        referenced = (
            await RecipeModel.get_or_none(id=ingredient.referenced_recipe_id)
            if ingredient.referenced_recipe_id
            else None
        )
        item["referenced_recipe"] = await recipe_data(referenced, _visited=visited) if referenced else None
        item["substitutions"] = []
        for substitution in await RecipeIngredientSubstitutionModel.filter(ingredient_id=ingredient.id).order_by(
            "position"
        ):
            sub = model_data(substitution)
            food = (
                await IngredientFoodModel.get_or_none(id=substitution.substitute_food_id)
                if substitution.substitute_food_id
                else None
            )
            sub["substitute_food"] = model_data(food) if food else None
            item["substitutions"].append(sub)
        data["recipe_ingredient"].append(item)
    data["recipe_instructions"] = []
    for instruction in await RecipeInstruction.filter(recipe_id=entry.id).order_by("position"):
        item = model_data(instruction)
        item["ingredient_references"] = await RecipeIngredientRefLink.filter(instruction_id=instruction.id).values()
        item["note_references"] = await RecipeNoteRefLink.filter(instruction_id=instruction.id).values()
        data["recipe_instructions"].append(item)
    return data


def _fields(model: type[Model], data: dict[str, Any], **owner: Any) -> dict[str, Any]:
    return {
        key: value for key, value in data.items() if key in model._meta.db_fields and key not in ("id", *owner)
    } | owner


async def replace_recipe_children(entry: RecipeModel, data: dict[str, Any], *, creating: bool) -> None:
    """Replace recipe-owned rows without ever attaching another recipe's children."""
    # The original recipe constructor creates settings/nutrition on every save.
    for key, model in (("nutrition", Nutrition), ("settings", RecipeSettings)):
        await model.filter(recipe_id=entry.id).delete()
        await model.create(**_fields(model, data.get(key) or {}, recipe_id=entry.id))

    for key, model in (("assets", RecipeAsset), ("notes", Note)):
        if data.get(key) is None and not creating:
            continue
        await model.filter(recipe_id=entry.id).delete()
        for item in data.get(key) or []:
            await model.create(**_fields(model, item, recipe_id=entry.id))

    # Extras are a dictionary rather than addressable child identities.
    await ApiExtras.filter(recipee_id=entry.id).delete()
    for key, value in (data.get("extras") or {}).items():
        await ApiExtras.create(recipee_id=entry.id, key_name=key, value=value)

    if data.get("recipe_instructions") is not None:
        instructions = await RecipeInstruction.filter(recipe_id=entry.id).values_list("id", flat=True)
        await RecipeIngredientRefLink.filter(instruction_id__in=instructions).delete()
        await RecipeNoteRefLink.filter(instruction_id__in=instructions).delete()
        await RecipeInstruction.filter(recipe_id=entry.id).delete()
        for position, item in enumerate(data.get("recipe_instructions") or []):
            instruction = await RecipeInstruction.create(
                **_fields(RecipeInstruction, item, recipe_id=entry.id, position=position)
            )
            for key, model in (
                ("ingredient_references", RecipeIngredientRefLink),
                ("note_references", RecipeNoteRefLink),
            ):
                for ref in item.get(key) or []:
                    await model.create(**_fields(model, ref, instruction_id=instruction.id))

    if data.get("recipe_ingredient") is not None:
        ingredients = await RecipeIngredientModel.filter(recipe_id=entry.id).values_list("id", flat=True)
        await RecipeIngredientSubstitutionModel.filter(ingredient_id__in=ingredients).delete()
        await RecipeIngredientModel.filter(recipe_id=entry.id).delete()
        for position, item in enumerate(data.get("recipe_ingredient") or []):
            values = _fields(RecipeIngredientModel, item, recipe_id=entry.id, position=position)
            for key, model in (
                ("food", IngredientFoodModel),
                ("unit", IngredientUnitModel),
                ("referenced_recipe", RecipeModel),
            ):
                if key not in item:
                    continue
                related = item[key]
                lookup = "slug" if model is RecipeModel else "id"
                if isinstance(related, dict):
                    if related.get("id") is not None:
                        lookup = "id"
                    identifier = related.get(lookup)
                    if identifier is None:
                        raise ValueError(f"Expected '{lookup}' to be provided for {key}")
                else:
                    identifier = related
                related_entry = (
                    await model.get_or_none(**{lookup: identifier, "group_id": entry.group_id}) if identifier else None
                )
                values[key + "_id"] = related_entry.id if related_entry else None
            ingredient = await RecipeIngredientModel.create(**values)
            substitutions = await resolve_substitutions(entry.group_id, item.get("substitutions"))
            for sub_position, (food_id, note) in enumerate(substitutions):
                await RecipeIngredientSubstitutionModel.create(
                    ingredient_id=ingredient.id, substitute_food_id=food_id, note=note, position=sub_position
                )
