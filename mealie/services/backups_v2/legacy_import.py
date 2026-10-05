"""Translate legacy backup documents into rows for the current database schema.

This operates on an exported document only. It never opens or migrates an old
application database and does not depend on its migration implementation.
"""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from slugify import slugify
from tortoise import Tortoise, fields

from mealie.core.config import get_app_settings
from mealie.db.models._model_base import TortoiseModel


def _uuid(value: Any) -> Any:
    try:
        return str(UUID(str(value)))
    except ValueError, TypeError:
        return value


def _new_row(**values: Any) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {"id": str(uuid4()), "created_at": now, "update_at": now, **values}


def _households(data: dict[str, list[dict[str, Any]]]) -> None:
    households = data.setdefault("households", [])
    preferences = data.setdefault("household_preferences", [])
    group_preferences = {row["group_id"]: row for row in data.get("group_preferences", [])}
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in households:
        by_group.setdefault(row["group_id"], []).append(row)
    settings = get_app_settings()
    for group in data.get("groups", []):
        group_id = group["id"]
        if group_id not in by_group:
            household = _new_row(
                name=settings.DEFAULT_HOUSEHOLD, slug=slugify(settings.DEFAULT_HOUSEHOLD), group_id=group_id
            )
            households.append(household)
            by_group[group_id] = [household]
        for household in by_group[group_id]:
            if not any(row["household_id"] == household["id"] for row in preferences):
                prefs = dict(group_preferences.get(group_id, {}))
                prefs.pop("id", None)
                prefs.pop("group_id", None)
                prefs["private_household"] = prefs.pop("private_group", True)
                preferences.append(_new_row(household_id=household["id"], **prefs))
    users = {row["id"]: row for row in data.get("users", [])}
    for rows in data.values():
        for row in rows:
            group_id = row.get("group_id")
            if group_id not in by_group or row.get("household_id"):
                continue
            owner = users.get(row.get("user_id"), {})
            row["household_id"] = owner.get("household_id") or by_group[group_id][0]["id"]
    for group in data.get("groups", []):
        if not any(row.get("group_id") == group["id"] for row in data.setdefault("ai_provider_settings", [])):
            data["ai_provider_settings"].append(_new_row(group_id=group["id"]))


def _ratings(data: dict[str, list[dict[str, Any]]]) -> None:
    ratings = data.setdefault("users_to_recipes", [])
    by_key = {(row["user_id"], row["recipe_id"]): row for row in ratings}
    for favorite in data.get("users_to_favorites", []):
        key = (favorite.get("user_id"), favorite.get("recipe_id"))
        if not all(key):
            continue
        if key not in by_key:
            by_key[key] = _new_row(user_id=key[0], recipe_id=key[1], rating=None, is_favorite=True)
            ratings.append(by_key[key])
        else:
            by_key[key]["is_favorite"] = True
    for recipe in data.get("recipes", []):
        existing = [row for row in ratings if row["recipe_id"] == recipe["id"]]
        if not any(row.get("rating") for row in existing) and recipe.get("rating"):
            for user in data.get("users", []):
                if user["group_id"] != recipe["group_id"]:
                    continue
                key = (user["id"], recipe["id"])
                if key not in by_key:
                    by_key[key] = _new_row(user_id=key[0], recipe_id=key[1], rating=None, is_favorite=False)
                    ratings.append(by_key[key])
                by_key[key]["rating"] = recipe["rating"]


def _query_filters(data: dict[str, list[dict[str, Any]]]) -> None:
    def ids(table: str, key: str, value: Any, target: str) -> list[str]:
        return sorted({str(row[target]) for row in data.get(table, []) if row.get(key) == value and row.get(target)})

    for table, is_cookbook in (("cookbooks", True), ("group_meal_plan_rules", False)):
        for row in data.get(table, []):
            if row.get("query_filter_string"):
                continue
            parts = []
            for category, path in (
                ("categories", "recipe_category.id"),
                ("tags", "tags.id"),
                ("tools", "tools.id"),
                ("households", "household_id"),
            ):
                if (is_cookbook and category == "households") or (not is_cookbook and category == "tools"):
                    continue
                suffix = {"categories": "category", "tags": "tag", "tools": "tool", "households": "household"}[category]
                link_table = f"{'cookbooks' if is_cookbook else 'plan_rules'}_to_{category}"
                source_key = (
                    "cookbook_id" if is_cookbook else "plan_rule_id" if category == "tags" else "group_plan_rule_id"
                )
                values = ids(link_table, source_key, row["id"], f"{suffix}_id")
                if not values:
                    continue
                op = "CONTAINS ALL"
                if category == "households" or (is_cookbook and not row.get(f"require_all_{category}", True)):
                    op = "IN"
                quoted = ",".join(f'"{value}"' for value in values)
                parts.append(f"{path} {op} [{quoted}]")
            row["query_filter_string"] = " AND ".join(parts)


def _household_history(data: dict[str, list[dict[str, Any]]]) -> None:
    history = data.setdefault("households_to_recipes", [])
    history_keys = {(row["household_id"], row["recipe_id"]) for row in history}
    for household in data.get("households", []):
        for recipe in data.get("recipes", []):
            key = (household["id"], recipe["id"])
            if recipe["group_id"] == household["group_id"] and recipe.get("last_made") and key not in history_keys:
                history.append(_new_row(household_id=key[0], recipe_id=key[1], last_made=recipe["last_made"]))
                history_keys.add(key)
        for table, link_table, foreign_key in (
            ("ingredient_foods", "households_to_ingredient_foods", "food_id"),
            ("tools", "households_to_tools", "tool_id"),
        ):
            links = data.setdefault(link_table, [])
            existing = {(row["household_id"], row[foreign_key]) for row in links}
            for row in data.get(table, []):
                pair = (household["id"], row["id"])
                if row["group_id"] == household["group_id"] and row.get("on_hand") and pair not in existing:
                    links.append({"household_id": pair[0], foreign_key: pair[1]})


def _label_settings(data: dict[str, list[dict[str, Any]]]) -> None:
    labels = {row["id"]: row for row in data.get("multi_purpose_labels", [])}
    shopping_lists = {row["id"]: row for row in data.get("shopping_lists", [])}
    links = data["shopping_lists_multi_purpose_labels"] = [
        row
        for row in data.get("shopping_lists_multi_purpose_labels", [])
        if (label := labels.get(row["label_id"]))
        and (shopping_list := shopping_lists.get(row["shopping_list_id"]))
        and label["group_id"] == shopping_list["group_id"]
    ]
    for shopping_list in data.get("shopping_lists", []):
        existing = {row["label_id"] for row in links if row["shopping_list_id"] == shopping_list["id"]}
        for label in data.get("multi_purpose_labels", []):
            if label["group_id"] == shopping_list["group_id"] and label["id"] not in existing:
                links.append(
                    _new_row(shopping_list_id=shopping_list["id"], label_id=label["id"], position=len(existing))
                )
                existing.add(label["id"])


def _standardize_units(data: dict[str, list[dict[str, Any]]]) -> None:
    from mealie.lang.locale_config import LOCALE_CONFIG
    from mealie.repos.repository_units import RepositoryUnit
    from mealie.repos.seed.seeders import IngredientUnitsSeeder

    repo = object.__new__(RepositoryUnit)
    repo._standardized_unit_map = {}
    for locale in LOCALE_CONFIG:
        for key, unit in IngredientUnitsSeeder.load_file(IngredientUnitsSeeder.get_file(locale)).items():
            for name in ("name", "plural_name", "abbreviation"):
                if value := unit.get(name):
                    repo._standardized_unit_map[value.strip().lower()] = key
    for unit in data.get("ingredient_units", []):
        repo._add_standardized_unit(unit)


def _model_defaults(data: dict[str, list[dict[str, Any]]]) -> None:
    for model in Tortoise.apps["models"].values():
        for row in data.get(model._meta.db_table, []):
            for name, column in model._meta.fields_db_projection.items():
                field = model._meta.fields_map[name]
                if column in row and row[column] is not None:
                    if isinstance(field, fields.UUIDField):
                        row[column] = _uuid(row[column])
                    elif enum_type := getattr(field, "enum_type", None):
                        if row[column] in enum_type.__members__:
                            row[column] = enum_type[row[column]].value
                    continue
                if name.endswith("_normalized"):
                    value = row.get(name.removesuffix("_normalized"))
                    row[column] = TortoiseModel.normalize(value) if value else None
                elif field.default is not None:
                    row[column] = field.default() if callable(field.default) else field.default
                elif getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
                    row[column] = datetime.now(UTC)
                elif field.null:
                    row[column] = None


def _clean_references(data: dict[str, list[dict[str, Any]]]) -> None:
    users = {row["id"] for row in data.get("users", [])}
    for table in ("recipes", "shopping_lists", "group_meal_plans"):
        for row in data.get(table, []):
            if row.get("user_id") in users:
                continue
            candidates = [user for user in data.get("users", []) if user["group_id"] == row.get("group_id")]
            if candidates:
                owner = next((user for user in candidates if user.get("admin")), candidates[0])
                row["user_id"] = owner["id"]
    # Removing a corrupt parent may invalidate a child, so continue to a fixed point.
    changed = True
    while changed:
        changed = False
        for model in Tortoise.apps["models"].values():
            table = model._meta.db_table
            rows = data.get(table, [])
            keep = []
            unique_relations: dict[str, set[Any]] = {name: set() for name in model._meta.o2o_fields}
            for row in rows:
                valid = True
                for name in model._meta.fk_fields | model._meta.o2o_fields:
                    relation = model._meta.fields_map[name]
                    key = model._meta.fields_db_projection[relation.source_field]
                    target = relation.related_model
                    target_key = target._meta.fields_db_projection[target._meta.pk_attr]
                    value = row.get(key)
                    if value is None or any(
                        parent.get(target_key) == value for parent in data.get(target._meta.db_table, [])
                    ):
                        continue
                    if relation.null:
                        row[key] = None
                    else:
                        valid = False
                        break
                if valid:
                    # Legacy scalar relationships could contain multiple rows;
                    # the former ORM exposed their first row as the scalar value.
                    for name, seen_values in unique_relations.items():
                        relation = model._meta.fields_map[name]
                        key = model._meta.fields_db_projection[relation.source_field]
                        value = row.get(key)
                        if value is not None and value in seen_values:
                            valid = False
                            break
                if valid:
                    for name, seen_values in unique_relations.items():
                        relation = model._meta.fields_map[name]
                        key = model._meta.fields_db_projection[relation.source_field]
                        seen_values.add(row.get(key))
                    keep.append(row)
            if len(keep) != len(rows):
                data[table] = keep
                changed = True
            for name in model._meta.m2m_fields:
                relation = model._meta.fields_map[name]
                target = relation.related_model
                parent_ids = {row.get(model._meta.pk_attr) for row in data.get(table, [])}
                target_ids = {row.get(target._meta.pk_attr) for row in data.get(target._meta.db_table, [])}
                rows = data.get(relation.through, [])
                # Older association tables allowed the same relationship more than
                # once. Preserve its first occurrence for the native unique pair.
                seen = set()
                links = []
                for row in rows:
                    pair = (row.get(relation.backward_key), row.get(relation.forward_key))
                    if pair[0] in parent_ids and pair[1] in target_ids and pair not in seen:
                        seen.add(pair)
                        links.append(row)
                data[relation.through] = links


def prepare_legacy_backup(source: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    data = deepcopy(source)
    for rows in data.values():
        for row in rows:
            for key, value in row.items():
                if key == "id" or key.endswith("_id"):
                    row[key] = _uuid(value)
    used_slugs: set[str] = set()
    for group in data.get("groups", []):
        slug = group.get("slug") or slugify(group["name"])
        base = slug
        index = 1
        while slug in used_slugs:
            slug = f"{base}-{index}"
            index += 1
        group["slug"] = slug
        used_slugs.add(slug)
    _households(data)
    _ratings(data)
    _household_history(data)
    _label_settings(data)
    _standardize_units(data)
    _model_defaults(data)
    _clean_references(data)
    _query_filters(data)
    return data
