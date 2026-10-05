"""Native asynchronous database models and nested application payload persistence."""

from __future__ import annotations

import inspect
import string
from datetime import UTC, datetime
from typing import Any, ClassVar, Self, get_args
from uuid import UUID

from pydantic import BaseModel
from slugify import slugify
from text_unidecode import unidecode
from tortoise import Model, fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import DoesNotExist
from tortoise.models import ModelMeta

NORMALIZE_PUNCTUATION = string.punctuation.replace("'", "").replace('"', "")
_NORMALIZE_PUNCTUATION_TABLE = str.maketrans(NORMALIZE_PUNCTUATION, " " * len(NORMALIZE_PUNCTUATION))


def _nested_schema(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for argument in get_args(annotation):
        if result := _nested_schema(argument):
            return result
    return None


def _payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


class MealieModelMeta(ModelMeta):
    """Expose native field metadata for query filters and model inspection."""

    def __getattr__(cls, name: str) -> Any:
        meta = type.__getattribute__(cls, "_meta")
        if name in meta.fields_map:
            return meta.fields_map[name]
        raise AttributeError(f"{cls.__name__!s} has no attribute {name!r}")


class TortoiseModel(Model, metaclass=MealieModelMeta):
    """Shared timestamps, normalization, and explicit asynchronous relation handling.

    Constructors never query the database. Application writes use ``create_from_data``
    and ``update_from_data`` so nested payloads are persisted on the supplied connection.
    ``schema_data`` resolves the relations required by an unchanged Pydantic schema.
    """

    id: Any = fields.IntField(primary_key=True)
    created_at = fields.DatetimeField(auto_now_add=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True)
    __filterable_fields__: ClassVar[set[str]] = {"id", "created_at", "update_at", "updated_at"}
    __association_proxies__: ClassVar[dict[str, list[str]]] = {}
    model_config: ClassVar[dict[str, Any]] = {}

    class Meta:
        abstract = True

    @property
    def updated_at(self) -> datetime:
        return self.update_at

    @updated_at.setter
    def updated_at(self, value: datetime) -> None:
        self.update_at = value

    @classmethod
    def normalize(cls, value: str) -> str:
        return unidecode(value).translate(_NORMALIZE_PUNCTUATION_TABLE).lower().strip()[:255]

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Any = None,
        force_create: bool = False,
        force_update: bool = False,
    ) -> None:
        changed = set(update_fields) if update_fields is not None else None
        for name in self._meta.fields_db_projection:
            if name.endswith("_normalized"):
                source = name.removesuffix("_normalized")
                value = getattr(self, source, None)
                setattr(self, name, self.normalize(value) if value is not None else None)
                if changed is not None and source in changed:
                    changed.add(name)
        if self.__class__.__name__ in {"Category", "Tag", "Tool"}:
            organizer_name = getattr(self, "name", None)
            if not organizer_name:
                raise ValueError("Name must not be empty")
            self.name = organizer_name.strip()
            self.slug = slugify(organizer_name.strip())
            if changed is not None and "name" in changed:
                changed.add("slug")
        if self.__class__.__name__ == "RecipeModel":
            if not getattr(self, "name", None):
                raise ValueError("Recipe name must not be empty")
            self.date_updated = datetime.now(UTC)
            if changed is not None:
                changed.add("date_updated")
        if changed is not None:
            changed.add("update_at")
        await super().save(using_db, changed, force_create, force_update)
        await self._update_parent_summaries(using_db)

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        await super().delete(using_db)
        await self._update_parent_summaries(using_db, deleted=True)

    async def _update_parent_summaries(self, using_db: BaseDBAsyncClient | None, *, deleted: bool = False) -> None:
        model_name = self.__class__.__name__
        if model_name == "ShoppingListItem":
            from .household.shopping_list import ShoppingList

            await (
                ShoppingList.filter(id=self.__dict__["shopping_list_id"])
                .using_db(using_db)
                .update(update_at=datetime.now(UTC))
            )
        elif model_name == "UserToRecipe":
            from .recipe.recipe import RecipeModel
            from .users.user_to_recipe import UserToRecipe

            recipe_id = self.__dict__["recipe_id"]
            rows = await UserToRecipe.filter(recipe_id=recipe_id, rating__gt=0).using_db(using_db).values("rating")
            ratings = [float(row["rating"]) for row in rows]
            rating = sum(ratings) / len(ratings) if ratings else None
            await RecipeModel.filter(id=recipe_id).using_db(using_db).update(rating=rating)
        elif model_name == "HouseholdToRecipe" and (last_made := getattr(self, "last_made", None)):
            from .recipe.recipe import RecipeModel

            recipe_id = self.__dict__["recipe_id"]
            recipe = await RecipeModel.filter(id=recipe_id).using_db(using_db).first()
            if recipe and (recipe.last_made is None or last_made > recipe.last_made):
                await RecipeModel.filter(id=recipe_id).using_db(using_db).update(last_made=last_made)
        elif model_name == "AIProvider" and deleted:
            from .group.ai_providers import AIProviderSettings

            for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
                await AIProviderSettings.filter(**{field: self.id}).using_db(using_db).update(**{field: None})

    @classmethod
    async def create_from_data(cls, data: dict[str, Any], using_db: BaseDBAsyncClient | None = None) -> Self:
        instance = cls()
        await instance.update_from_data(data, using_db=using_db)
        return instance

    async def update_from_data(self, data: dict[str, Any], using_db: BaseDBAsyncClient | None = None) -> Self:
        data = dict(_payload(data))
        creating = not self._saved_in_db
        model_name = self.__class__.__name__
        if model_name == "User":
            await self._prepare_user(data, using_db)
            if not creating:
                data.pop("password", None)
        excluded = set(self.model_config.get("exclude", ())) & self._meta.fetch_fields
        handled_explicitly = {
            "RecipeModel": {"assets", "notes", "nutrition", "recipe_ingredient", "recipe_instructions", "settings"},
            "RecipeInstruction": {"ingredient_references", "note_references"},
            "IngredientFoodModel": {"substitutions", "households_with_ingredient_food"},
            "RecipeIngredientModel": {"substitutions"},
            "Tool": {"households_with_tool"},
        }
        for name in excluded - handled_explicitly.get(model_name, set()):
            data.pop(name, None)
        if "key" in data and "key_name" in self._meta.fields_db_projection:
            data["key_name"] = data.pop("key")
        context_group_id = data.get("group_id") or getattr(self, "_context_group_id", None)
        if context_group_id is None and "group_id" in self._meta.fields_db_projection:
            context_group_id = getattr(self, "group_id", None)
        self._context_group_id = context_group_id
        if model_name == "RecipeModel" and creating:
            data.setdefault("nutrition", {})
            data.setdefault("settings", {})
        elif model_name == "RecipeModel":
            # Ratings are maintained from UserToRecipe; recipe edits cannot set them.
            data.pop("rating", None)
        for name in self._meta.fields_db_projection:
            if name in data and (name != self._meta.pk_attr or creating):
                if name == self._meta.pk_attr and data[name] is None:
                    continue
                setattr(self, name, self._meta.fields_map[name].to_python_value(data[name]))
        if context_group_id is None and "group_id" in self.__association_proxies__:
            context_group_id = await self._get_attribute("group_id")
            self._context_group_id = context_group_id
        await self._validate_scalar_references(data, context_group_id, using_db)
        # Resolve references before saving the parent; never manufacture a record for an unknown id.
        for name in self._meta.fk_fields | self._meta.o2o_fields:
            if name not in data:
                continue
            relation: Any = self._meta.fields_map[name]
            id_name = relation.source_field
            if id_name in data:
                continue
            value = _payload(data[name])
            if value is None:
                if relation.null:
                    setattr(self, id_name, None)
                continue
            related = await self._resolve_reference(relation.related_model, value, context_group_id, using_db)
            if related is not None:
                setattr(self, name, related)
            elif relation.null:
                setattr(self, id_name, None)
            else:
                raise ValueError(f"Invalid {name} reference")
        await self.save(using_db=using_db)
        for name in self._meta.m2m_fields:
            if name not in data:
                continue
            relation = self._meta.fields_map[name]
            related_rows = []
            for value in data[name] or []:
                row = await self._resolve_reference(relation.related_model, _payload(value), context_group_id, using_db)
                if row is not None:
                    related_rows.append(row)
            manager = getattr(self, name)
            await manager.clear(using_db=using_db)
            if related_rows:
                await manager.add(*related_rows, using_db=using_db)
        await self._update_children(data, context_group_id, using_db)
        return self

    async def _update_children(
        self, data: dict[str, Any], context_group_id: UUID | None, using_db: BaseDBAsyncClient | None
    ) -> None:
        model_name = self.__class__.__name__
        for name in self._meta.backward_fk_fields | self._meta.backward_o2o_fields:
            if name not in data:
                continue
            relation: Any = self._meta.fields_map[name]
            target = relation.related_model
            foreign_key = relation.relation_field
            rows = data[name]
            if name in {"extras", "request_headers", "request_params"} and isinstance(rows, dict):
                rows = [{"key_name": key, "value": value} for key, value in rows.items()]
            if name in self._meta.backward_o2o_fields:
                rows = [rows or {}]
            rows = [_payload(row) for row in rows or []]
            if name == "substitutions":
                from .recipe.ingredient import resolve_substitutions

                rows = [
                    {"substitute_food_id": food_id, "note": note}
                    for food_id, note in await resolve_substitutions(
                        using_db,
                        context_group_id,
                        rows,
                        exclude_food_id=self.pk if model_name == "IngredientFoodModel" else None,
                    )
                ]
            existing = await target.filter(**{foreign_key: self.pk}).using_db(using_db)
            existing_by_id = {str(row.pk): row for row in existing}
            keep_ids = {str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id")}
            # Delete removed children first, so unique constraints also work during replacement.
            for row in existing:
                if str(row.pk) not in keep_ids:
                    await row.delete(using_db=using_db)
            for position, row_data in enumerate(rows):
                if not isinstance(row_data, dict):
                    continue
                row_data = dict(row_data)
                child = existing_by_id.get(str(row_data.get("id")))
                if child is None:
                    child = target()
                    if "id" in target.model_config.get("exclude", ()):
                        row_data.pop("id", None)
                row_data[foreign_key] = self.pk
                child._context_group_id = context_group_id
                if "position" in target._meta.fields_db_projection:
                    row_data["position"] = position
                await child.update_from_data(row_data, using_db=using_db)

    async def _validate_scalar_references(
        self, data: dict[str, Any], group_id: UUID | None, using_db: BaseDBAsyncClient | None
    ) -> None:
        if group_id is None:
            return
        for name in self._meta.fk_fields | self._meta.o2o_fields:
            field: Any = self._meta.fields_map[name]
            raw_name = field.source_field
            if raw_name not in data or data[raw_name] is None:
                continue
            target = field.related_model
            if "group_id" not in target._meta.fields_db_projection and "group_id" not in target.__association_proxies__:
                continue
            related = await target.filter(pk=data[raw_name]).using_db(using_db).first()
            if related is None or str(await related._get_attribute("group_id")) != str(group_id):
                raise ValueError(f"Invalid {name} reference for this group")

    @classmethod
    async def _resolve_reference(
        cls,
        target: type[TortoiseModel],
        value: Any,
        group_id: UUID | None,
        using_db: BaseDBAsyncClient | None,
    ) -> TortoiseModel | None:
        if isinstance(value, TortoiseModel):
            if group_id is not None and (
                "group_id" in target._meta.fields_db_projection or "group_id" in target.__association_proxies__
            ):
                if str(await value._get_attribute("group_id")) != str(group_id):
                    raise ValueError("Related record belongs to a different group")
            return value
        query = target.all().using_db(using_db)
        if group_id is not None and "group_id" in target._meta.fields_db_projection:
            query = query.filter(group_id=group_id)
        if isinstance(value, dict):
            identifier = value.get("id")
            if identifier is not None:
                existing = await query.filter(pk=identifier).first()
                if existing is not None:
                    return existing
                if target.__name__ not in {"Category", "Tag", "Tool"}:
                    return None
            if target.__name__ in {"Category", "Tag", "Tool"} and value.get("name"):
                value = dict(value)
                value.pop("id", None)
                value["slug"] = value.get("slug") or slugify(value["name"])
                existing = await query.filter(slug=value["slug"]).first()
                if existing:
                    return existing
                if group_id:
                    value["group_id"] = group_id
                return await target.create_from_data(value, using_db=using_db)
            lookup = target.model_config.get("get_attr", "id")
            if value.get(lookup) is not None:
                return await query.filter(**{lookup: value[lookup]}).first()
            return None
        if isinstance(value, str) and target.__name__ == "Household":
            return await query.filter(slug=value).first()
        try:
            return await query.filter(pk=value).first()
        except ValueError, TypeError:
            if "slug" in target._meta.fields_db_projection:
                return await query.filter(slug=value).first()
            return None

    async def _prepare_user(self, data: dict[str, Any], using_db: BaseDBAsyncClient | None) -> None:
        from mealie.core.config import get_app_settings

        from .group.group import Group
        from .household.household import Household

        settings = get_app_settings()
        if "group_id" not in data and (not self._saved_in_db or "group" in data):
            name = data.pop("group", None) or settings.DEFAULT_GROUP
            if isinstance(name, Model):
                data["group_id"] = name.pk
            else:
                group = await Group.filter(name=name).using_db(using_db).first()
                if group is None:
                    raise ValueError(f"Group {name} does not exist; cannot create user")
                data["group_id"] = group.id
        else:
            data.pop("group", None)
        if "household_id" not in data and (not self._saved_in_db or "household" in data):
            name = data.pop("household", None) or settings.DEFAULT_HOUSEHOLD
            group_id = data.get("group_id", getattr(self, "group_id", None))
            if isinstance(name, Model):
                data["household_id"] = name.pk
            else:
                household = await Household.filter(name=name, group_id=group_id).using_db(using_db).first()
                if household is None:
                    raise ValueError(f'Household "{name}" does not exist on group {group_id}; cannot create user')
                data["household_id"] = household.id
        else:
            data.pop("household", None)
        if not data.get("username", getattr(self, "username", None)):
            data["username"] = data.get("full_name", getattr(self, "full_name", None))
        if data.get("admin", getattr(self, "admin", False)):
            for name in ("can_manage_household", "can_manage", "can_invite", "can_organize", "advanced"):
                data[name] = True

    async def _get_attribute(self, name: str) -> Any:
        if name in self.__association_proxies__:
            value: Any = self
            for component in self.__association_proxies__[name]:
                if value is None:
                    return None
                value = (
                    await value._get_attribute(component)
                    if isinstance(value, TortoiseModel)
                    else getattr(value, component, None)
                )
            return value
        if name == "group_slug":
            group = await self._get_attribute("group")
            return group.slug if group else None
        if name == "household_slug":
            household = await self._get_attribute("household")
            return household.slug if household else None
        try:
            value = getattr(self, name)
            if name in self._meta.m2m_fields | self._meta.backward_fk_fields:
                if value._fetched:
                    return list(value)
                return list(await value.all())
            if inspect.isawaitable(value):
                value = await value
            return value
        except DoesNotExist:
            return None

    async def schema_data(
        self, schema: type[BaseModel], _seen: set[tuple[type, Any, type]] | None = None
    ) -> dict[str, Any]:
        seen = set() if _seen is None else set(_seen)
        marker = (type(self), self.pk, schema)
        if marker in seen:
            return {
                name: getattr(self, name) for name in schema.model_fields if name in self._meta.fields_db_projection
            }
        seen.add(marker)
        data: dict[str, Any] = {}
        for name, field in schema.model_fields.items():
            if (
                name not in self._meta.fields_map
                and name not in self.__association_proxies__
                and not hasattr(type(self), name)
            ):
                continue
            value = await self._get_attribute(name)
            nested = _nested_schema(field.annotation)
            if isinstance(value, TortoiseModel):
                if nested is not None:
                    value = await value.schema_data(nested, seen)
                elif name in {"group", "household"}:
                    value = value.name
            elif isinstance(value, list):
                if name in {"extras", "request_headers", "request_params"}:
                    value = {row.key_name: row.value for row in value}
                elif nested is not None:
                    value = [
                        await row.schema_data(nested, seen) if isinstance(row, TortoiseModel) else row for row in value
                    ]
                elif name in {"households_with_tool", "households_with_ingredient_food"}:
                    value = [row.slug for row in value]
            data[name] = value
        return data

    async def to_schema(self, schema: type[BaseModel]) -> BaseModel:
        return schema.model_validate(await self.schema_data(schema))
