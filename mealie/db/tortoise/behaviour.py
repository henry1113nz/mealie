"""What the SQLAlchemy models did implicitly, done explicitly for Tortoise (stage S2).

- relation_paths: SQLAlchemy loaded a relation lazily when a schema read it; Tortoise raises
  unless it was fetched first.
- write_children: auto_init created and updated nested children from dicts.
- delete_with_relations: relationship settings deleted children or cleared their foreign keys.
- scope_filter: several group_id / household_id attributes are association proxies.
"""

import types
import typing
from typing import Any

from pydantic import BaseModel
from tortoise.models import Model

from .models import CASCADE_DELETE, NULLIFY_ON_DELETE, PROXIES


def _nested_schema(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if typing.get_origin(annotation) in (list, set, tuple, typing.Union, types.UnionType):
        for arg in typing.get_args(annotation):
            if found := _nested_schema(arg):
                return found
    return None


def relation_paths(model: type[Model], schema: type[BaseModel], prefix: str = "", depth: int = 0) -> list[str]:
    """Prefetch paths for every relation the schema reads from the model."""
    if depth > 3:
        return []
    paths: list[str] = []
    for name, field in schema.model_fields.items():
        if name not in model._meta.fetch_fields:
            continue
        paths.append(prefix + name)
        nested = _nested_schema(field.annotation)
        related = getattr(model._meta.fields_map[name], "related_model", None)
        if nested and related:
            paths.extend(relation_paths(related, nested, f"{prefix}{name}__", depth + 1))
    return paths


def writable(model: type[Model], data: dict[str, Any]) -> dict[str, Any]:
    meta = model._meta
    return {k: v for k, v in data.items() if k in meta.fields_map and k not in meta.fetch_fields}


async def write_children(obj: Model, data: dict[str, Any]) -> None:
    """One-to-one children are updated or created; one-to-many lists replace the stored rows
    (matched by id, missing ones deleted, new ones created), as auto_init did."""
    meta = obj._meta
    for name, value in data.items():
        if name in meta.backward_o2o_fields and isinstance(value, dict):
            field = meta.fields_map[name]
            child_model, fk = field.related_model, field.relation_field
            values = {k: v for k, v in writable(child_model, value).items() if k not in ("id", fk)}
            existing = await child_model.filter(**{fk: obj.pk}).first()
            if existing:
                existing.update_from_dict(values)
                await existing.save()
            else:
                await child_model.create(**values, **{fk: obj.pk})
        elif name in meta.backward_fk_fields and isinstance(value, list):
            field = meta.fields_map[name]
            child_model, fk = field.related_model, field.relation_field
            stored = {child.pk: child for child in await child_model.filter(**{fk: obj.pk})}
            kept = set()
            for item in value:
                values = {k: v for k, v in writable(child_model, dict(item)).items() if k != fk}
                child = stored.get(values.get("id"))
                if child:
                    kept.add(child.pk)
                    child.update_from_dict(values)
                    await child.save()
                else:
                    if values.get("id") is None:
                        values.pop("id", None)
                    await child_model.create(**values, **{fk: obj.pk})
            for pk, child in stored.items():
                if pk not in kept:
                    await delete_with_relations(child)


async def delete_with_relations(obj: Model) -> None:
    meta = obj._meta
    name = type(obj).__name__
    for relation in CASCADE_DELETE.get(name, []):
        field = meta.fields_map[relation]
        for child in await field.related_model.filter(**{field.relation_field: obj.pk}):
            await delete_with_relations(child)
    for relation in NULLIFY_ON_DELETE.get(name, []):
        field = meta.fields_map[relation]
        await field.related_model.filter(**{field.relation_field: obj.pk}).update(**{field.relation_field: None})
    for relation in meta.m2m_fields:
        await getattr(obj, relation).clear()
    await obj.delete()


def scope_filter(model: type[Model], **scope: Any) -> dict[str, Any]:
    """Filter kwargs for group_id / household_id, following association proxies.

    Raises instead of dropping a scope the model cannot express.
    """
    result: dict[str, Any] = {}
    for key, value in scope.items():
        if value is None:
            continue
        if key in model._meta.fields_map:
            result[key] = value
        elif key in PROXIES.get(model.__name__, {}):
            result[PROXIES[model.__name__][key]] = value
        else:
            raise ValueError(f"{model.__name__} cannot be scoped by {key}")
    return result
