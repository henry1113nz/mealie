from __future__ import annotations

import random
import shutil
from collections.abc import Iterable
from math import ceil
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from tortoise import Model, fields
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from mealie.assets import users as users_assets
from mealie.core.config import get_app_settings
from mealie.db.models.group.group import Group
from mealie.db.models.household.household import Household
from mealie.db.models.users import User
from mealie.db.models.users.password_reset import PasswordResetModel
from mealie.db.models.users.user_to_recipe import UserToRecipe
from mealie.db.models.users.users import LongLiveToken
from mealie.schema._mealie import MealieModel
from mealie.schema.response.pagination import OrderDirection, PaginationBase, PaginationQuery
from mealie.schema.user.user import PrivateUser, UserRatingOut

from . import _users_coexistence as bridge
from ._utils import NOT_SET, NotSet

type DatabaseSession = BaseDBAsyncClient


class AsyncUserRepository[Schema: MealieModel, DBModel: Model]:
    """Native async persistence for user models on the owning connection."""

    def __init__(
        self,
        session: DatabaseSession,
        primary_key: str,
        sql_model: type[DBModel],
        schema: type[Schema],
        *,
        group_id: UUID | None | NotSet,
    ) -> None:
        if group_id is NOT_SET:
            raise ValueError("group_id must be set")
        self.session = session
        self.primary_key = primary_key
        self.model = sql_model
        self.schema = schema
        self.group_id = UUID(str(group_id)) if group_id else None
        self.household_id: UUID | None = None

    async def _query(self) -> QuerySet[DBModel]:
        query = self.model.all()
        if self.group_id:
            if self.model is User:
                query = query.filter(group_id=self.group_id)
            elif self.model is UserToRecipe:
                query = query.filter(recipe__group_id=self.group_id)
            else:
                query = query.filter(user__group_id=self.group_id)
        return query

    async def _serialize(self, entry: Model, schema: type[MealieModel] | None = None) -> Any:
        data = {key: getattr(entry, key) for key in entry._meta.db_fields}
        if isinstance(entry, User):
            group = await Group.get_or_none(id=entry.group_id)
            household = await Household.get_or_none(id=entry.household_id)
            data.update(
                group=group.name if group else None,
                group_slug=group.slug if group else None,
                household=household.name if household else None,
                household_slug=household.slug if household else None,
                tokens=await LongLiveToken.filter(user_id=entry.id).values("id", "name", "created_at"),
            )
        elif "user" in (schema or self.schema).model_fields:
            user = await User.get(id=entry.user_id)
            data["user"] = await self._serialize(user, PrivateUser)
        return (schema or self.schema).model_validate(data)

    async def _query_one(self, match_value: Any, match_key: str | None = None) -> DBModel:
        return await (await self._query()).get(**{match_key or self.primary_key: match_value})

    async def get_one(
        self,
        value: Any,
        key: str | None = None,
        any_case: bool = False,
        override_schema: type[MealieModel] | None = None,
    ) -> Any:
        key = key or self.primary_key
        if any_case:
            key += "__iexact"
        entry = await (await self._query()).filter(**{key: value}).get_or_none()
        return await self._serialize(entry, override_schema) if entry else None

    async def multi_query(
        self,
        query_by: dict[str, Any],
        start: int = 0,
        limit: int | None = None,
        override_schema: type[MealieModel] | None = None,
        order_by: str | None = None,
    ) -> list[Schema]:
        query = (await self._query()).filter(**query_by).offset(start)
        if limit is not None:
            query = query.limit(limit)
        if order_by:
            query = query.order_by(f"-{order_by}")
        return [await self._serialize(entry, override_schema) for entry in await query]

    async def get_all(
        self,
        limit: int | None = None,
        order_by: str | None = None,
        order_descending: bool = True,
        override: type[MealieModel] | None = None,
    ) -> list[Schema]:
        page = await self.page_all(
            PaginationQuery(
                per_page=limit or -1,
                order_by=order_by,
                order_direction=OrderDirection.desc if order_descending else OrderDirection.asc,
            ),
            override=override,
        )
        return page.items

    async def page_all(
        self, pagination: PaginationQuery, override: type[MealieModel] | None = None, search: str | None = None
    ) -> PaginationBase[Schema]:
        if search:
            # User schemas do not define searchable properties, as before C3.
            raise AttributeError("Not Implemented")
        paging = pagination.model_copy()
        try:
            identifiers = await self._query_identifiers(paging)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if paging.order_by == "random":
            ranks = list(range(len(identifiers)))
            random.Random(paging.pagination_seed).shuffle(ranks)
            identifiers = [value for _, value in sorted(zip(ranks, identifiers, strict=True))]
        count = len(identifiers)
        if paging.per_page == -1:
            paging.per_page = count
        pages = ceil(count / paging.per_page) if paging.per_page else 0
        if paging.page == -1:
            paging.page = pages
        paging.page = max(1, paging.page)
        start = (paging.page - 1) * paging.per_page
        identifiers = identifiers[start : start + paging.per_page]
        entries = {str(entry.pk): entry for entry in await (await self._query()).filter(pk__in=identifiers)}
        items = [
            await self._serialize(
                entries[str(UUID(str(key))) if isinstance(self.model._meta.pk, fields.UUIDField) else str(key)],
                override,
            )
            for key in identifiers
        ]
        return PaginationBase(page=paging.page, per_page=paging.per_page, total=count, total_pages=pages, items=items)

    async def _query_identifiers(self, pagination: PaginationQuery) -> list[Any]:
        return await bridge.query_ids(self.model.__name__, self.group_id, pagination)

    async def count_all(self, match_key: str | None = None, match_value: Any = None) -> int:
        query = await self._query()
        if match_key is not None and match_value is not None:
            query = query.filter(**{match_key: match_value})
        return await query.count()

    async def _prepare(self, data: dict[str, Any], *, creating: bool, entry: DBModel | None = None) -> dict[str, Any]:
        result = {key: value for key, value in data.items() if key in self.model._meta.db_fields}
        if not creating or self.model is not User or result.get("id") is None:
            result.pop("id", None)
        return result

    async def _after_write(self, entry: DBModel) -> None:
        pass

    async def create(self, data: Schema | BaseModel | dict[str, Any]) -> Schema:
        values = data.copy() if isinstance(data, dict) else data.model_dump()
        async with in_transaction("default"):
            entry = await self.model.create(**await self._prepare(values, creating=True))
            await self._after_write(entry)
            return await self._serialize(entry)

    async def create_many(self, data: Iterable[Schema | dict[str, Any]]) -> list[Schema]:
        async with in_transaction("default"):
            return [await self.create(item) for item in data]

    async def update(self, match_value: Any, new_data: dict[str, Any] | BaseModel) -> Schema:
        values = new_data.copy() if isinstance(new_data, dict) else new_data.model_dump()
        async with in_transaction("default"):
            entry = await self._query_one(match_value)
            entry.update_from_dict(await self._prepare(values, creating=False, entry=entry))
            await entry.save()
            await self._after_write(entry)
            return await self._serialize(entry)

    async def update_many(self, data: Iterable[Schema | dict[str, Any]]) -> list[Schema]:
        by_id = {str(item["id"] if isinstance(item, dict) else item.id): item for item in data}
        async with in_transaction("default"):
            entries = await (await self._query()).filter(pk__in=list(by_id))
            return [await self.update(getattr(entry, self.primary_key), by_id[str(entry.pk)]) for entry in entries]

    async def patch(self, match_value: Any, new_data: dict[str, Any] | BaseModel) -> Schema:
        entry = await self._query_one(match_value)
        original = (await self._serialize(entry)).model_dump()
        original.update(new_data if isinstance(new_data, dict) else new_data.model_dump())
        return await self.update(match_value, original)

    async def delete(self, value: Any, match_key: str | None = None) -> Schema:
        async with in_transaction("default"):
            entry = await self._query_one(value, match_key)
            result = await self._serialize(entry)
            await entry.delete()
            await self._after_write(entry)
            return result

    async def delete_many(self, values: Iterable[Any]) -> list[Schema]:
        entries = await (await self._query()).filter(pk__in=list(values))
        async with in_transaction("default"):
            return [await self.delete(getattr(entry, self.primary_key)) for entry in entries]

    async def delete_all(self) -> None:
        await self.delete_many(await (await self._query()).values_list("id", flat=True))


class RepositoryUsers(AsyncUserRepository[PrivateUser, User]):
    async def _sync_tokens(self, user_id: UUID, tokens: Any) -> None:
        if not isinstance(tokens, list):
            raise ValueError("tokens must be a list")
        current = {token.id: token for token in await LongLiveToken.filter(user_id=user_id)}
        retained = {int(token["id"]): token for token in tokens}
        if retained.keys() - current.keys():
            raise ValueError("Token does not belong to this user")
        for token_id, data in retained.items():
            token = current[token_id]
            # UserOut exposes token metadata, never token secrets or ownership.
            changed = []
            for field in ("name", "created_at"):
                if field in data and data[field] != getattr(token, field):
                    setattr(token, field, data[field])
                    changed.append(field)
            if changed:
                await token.save(update_fields=[*changed, "update_at"])
        await LongLiveToken.filter(user_id=user_id).exclude(id__in=list(retained)).delete()

    async def _prepare(self, data: dict[str, Any], *, creating: bool, entry: User | None = None) -> dict[str, Any]:
        settings = get_app_settings()
        group_name = settings.DEFAULT_GROUP if data.get("group") is None else data["group"]
        household_name = settings.DEFAULT_HOUSEHOLD if data.get("household") is None else data["household"]
        group = await Group.get_or_none(name=group_name)
        if not group:
            raise ValueError(f"Group {group_name} does not exist; cannot create user")
        household = await Household.get_or_none(name=household_name, group_id=group.id)
        if not household:
            raise ValueError(
                f'Household "{household_name}" does not exist on group "{group_name}" ({group.id}); cannot create user'
            )
        values = await super()._prepare(data, creating=creating)
        values.update(group_id=group.id, household_id=household.id)
        if entry is not None:
            # Legacy updates accept explicit foreign-key changes when the named
            # relationship is unchanged (e.g. administrative group reassignment).
            if group.id == entry.group_id and "group_id" in data:
                values["group_id"] = data["group_id"]
            if UUID(str(household.id)) == entry.household_id and "household_id" in data:
                values["household_id"] = data["household_id"]
        values["username"] = data.get("full_name") if data.get("username") is None else data["username"]
        if not creating:
            values.pop("password", None)
        if values.get("admin"):
            values.update(can_manage_household=True, can_manage=True, can_invite=True, can_organize=True, advanced=True)
        if "tokens" in data:
            if entry is not None:
                await self._sync_tokens(entry.id, data["tokens"])
            elif data["tokens"] != []:
                raise ValueError("New users cannot contain existing tokens")
        return values

    async def create(self, data: PrivateUser | BaseModel | dict[str, Any]) -> PrivateUser:
        user = await super().create(data)
        shutil.copy(
            random.choice([users_assets.img_random_1, users_assets.img_random_2, users_assets.img_random_3]),
            user.directory() / "profile.webp",
        )
        return user

    async def update(self, match_value: Any, new_data: dict[str, Any] | BaseModel) -> PrivateUser:
        if get_app_settings().IS_DEMO:
            user = await self.get_one(match_value)
            if user and user.is_default_user:
                return user
        return await super().update(match_value, new_data)

    async def update_password(self, id: Any, password: str) -> PrivateUser:
        async with in_transaction("default"):
            entry = await self._query_one(id)
            if get_app_settings().IS_DEMO:
                user = await self._serialize(entry)
                if user.is_default_user:
                    return user
            entry.update_password(password)
            await entry.save(update_fields=["password", "tokens_valid_after", "update_at"])
            await self._after_write(entry)
            return await self._serialize(entry)

    async def delete(self, value: Any, match_key: str | None = None) -> PrivateUser:
        async with in_transaction("default"):
            user = await self._query_one(value, match_key)
            result = await self._serialize(user)
            if get_app_settings().IS_DEMO and result.is_default_user:
                return result
            recipe_ids = await UserToRecipe.filter(user_id=user.id).values_list("recipe_id", flat=True)
            await bridge.delete_user_dependents(user.id)
            # The existing Alembic foreign keys have no ON DELETE CASCADE.
            await LongLiveToken.filter(user_id=user.id).delete()
            await PasswordResetModel.filter(user_id=user.id).delete()
            await UserToRecipe.filter(user_id=user.id).delete()
            await user.delete()
            for recipe_id in recipe_ids:
                await bridge.refresh_recipe_rating(recipe_id)
            await self._after_write(user)
        shutil.rmtree(PrivateUser.get_directory(result.id))
        return result

    async def get_by_username(self, username: str) -> PrivateUser | None:
        return await self.get_one(username, "username")

    async def get_locked_users(self) -> list[PrivateUser]:
        return [await self._serialize(user) for user in await (await self._query()).filter(locked_at__isnull=False)]


class RepositoryUserRatings(AsyncUserRepository[UserRatingOut, UserToRecipe]):
    async def _after_write(self, entry: UserToRecipe) -> None:
        await bridge.refresh_recipe_rating(entry.recipe_id)
        await super()._after_write(entry)

    async def get_by_user(self, user_id: UUID, favorites_only: bool = False) -> list[UserRatingOut]:
        return await self.multi_query({"user_id": user_id, **({"is_favorite": True} if favorites_only else {})})

    async def get_by_recipe(self, recipe_id: UUID, favorites_only: bool = False) -> list[UserRatingOut]:
        return await self.multi_query({"recipe_id": recipe_id, **({"is_favorite": True} if favorites_only else {})})

    async def get_by_user_and_recipe(self, user_id: UUID, recipe_id: UUID) -> UserRatingOut | None:
        results = await self.multi_query({"user_id": user_id, "recipe_id": recipe_id})
        return results[0] if results else None
