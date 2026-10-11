"""Shared normalization and transactional deletion for recipe-domain models."""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from slugify import slugify
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from mealie.db.models._tortoise_base import TortoiseBase


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_today() -> date:
    return utc_now().date()


class RecipeBase(TortoiseBase):
    class Meta:
        abstract = True

    def __init__(self, **kwargs: Any) -> None:
        if self._meta.db_table in {"categories", "tags"} and "name" in kwargs:
            name = kwargs["name"].strip()
            assert name != ""
            kwargs["name"] = name
            kwargs.setdefault("slug", slugify(name))
        if self._meta.db_table == "tools" and "name" in kwargs:
            kwargs.setdefault("slug", slugify(kwargs["name"]))
        super().__init__(**kwargs)
        # Tortoise applies defaults after constructor fields. Reapply the source
        # values so nullable normalization defaults do not overwrite them.
        for key in self._meta.fields:
            if key.endswith("_normalized"):
                source = key.removesuffix("_normalized")
                value = getattr(self, source, None)
                setattr(self, key, self.normalize(value) if value is not None else None)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "name" and self._meta.db_table in {"recipes", "categories", "tags"}:
            assert value != ""
        normalized = f"{key}_normalized"
        if normalized in self._meta.fields:
            super().__setattr__(normalized, self.normalize(value) if value is not None else None)
        super().__setattr__(key, value)

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: Iterable[str] | None = None,
        force_create: bool = False,
        force_update: bool = False,
    ) -> None:
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update(
                f"{name}_normalized" for name in tuple(update_fields) if f"{name}_normalized" in self._meta.fields
            )
        await super().save(using_db, update_fields, force_create, force_update)

    async def delete(self, using_db: BaseDBAsyncClient | None = None) -> None:
        from mealie.repos._recipes_coexistence import delete_recipe_dependents

        if using_db is not None:
            await delete_recipe_dependents(self, using_db)
            await super().delete(using_db=using_db)
        else:
            async with in_transaction("default") as connection:
                await delete_recipe_dependents(self, connection)
                await super().delete(using_db=connection)
