"""Async user persistence used by the incremental authentication cutover."""

from __future__ import annotations

import random
import shutil
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from tortoise.transactions import in_transaction

from mealie.assets import users as users_assets
from mealie.core.config import get_app_settings
from mealie.db.tortoise_models import AuthMethod, Group, Household, User
from mealie.db.tortoise_models.remaining import (
    GroupInviteToken,
    GroupPreferencesModel,
    HouseholdPreferencesModel,
    LongLiveToken,
    PasswordResetModel,
)
from mealie.schema.user.user import AuthMethod as SchemaAuthMethod
from mealie.schema.user.user import PrivateUser


def _uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _looks_uuid(value: Any) -> bool:
    try:
        _uuid(value)
    except TypeError, ValueError:
        return False
    return True


async def serialize_user(user: User) -> PrivateUser:
    """Materialize the same user fields the legacy ORM bridge exposed."""
    await user.fetch_related("group", "household", "long_live_tokens_user_id_related")
    group = user.group
    household = user.household
    tokens = [
        {
            "id": token.id,
            "name": token.name,
            "created_at": token.created_at,
        }
        for token in user.long_live_tokens_user_id_related
    ]
    values = {
        **{
            field: getattr(user, field)
            for field in User._meta.fields_db_projection
            if field in PrivateUser.model_fields and field not in {"group_id", "household_id", "owned_recipes_id"}
        },
        "group": group.name,
        "group_id": user.group_id,
        "group_slug": group.slug or "",
        "household": household.name if household else "",
        "household_id": user.household_id,
        "household_slug": household.slug or "" if household else "",
        "tokens": tokens,
    }
    auth_method = user.auth_method
    auth_method_name = auth_method.name if isinstance(auth_method, AuthMethod) else str(auth_method)
    values["auth_method"] = SchemaAuthMethod[auth_method_name]
    return PrivateUser.model_validate(values)


class TortoiseUserRepository:
    """Async user queries and mutations; every write uses Tortoise transactions."""

    @staticmethod
    def create_default_profile_image(user_id: Any) -> None:
        images = [users_assets.img_random_1, users_assets.img_random_2, users_assets.img_random_3]
        shutil.copy(random.choice(images), PrivateUser.get_directory(user_id) / "profile.webp")

    async def get_one(self, value: Any, key: str = "id", *, any_case: bool = False) -> PrivateUser | None:
        query = User.filter(**{f"{key}__iexact" if any_case and key in {"username", "email"} else key: value})
        user = await query.first()
        return await serialize_user(user) if user else None

    async def get_by_username(self, username: str) -> PrivateUser | None:
        return await self.get_one(username, "username", any_case=True)

    async def create(self, data: dict[str, Any], *, connection=None) -> PrivateUser:
        values = dict(data)
        values.setdefault("id", uuid4())
        group_value = values.pop("group_id", values.pop("group", None))
        household_value = values.pop("household_id", values.pop("household", None))
        if group_value is None or not isinstance(group_value, UUID):
            group_query = (
                Group.filter(id=_uuid(group_value))
                if group_value and _looks_uuid(group_value)
                else Group.filter(name=group_value or get_app_settings().DEFAULT_GROUP)
            )
            if connection is not None:
                group_query = group_query.using_db(connection)
            group = await group_query.first()
            if group is None:
                raise ValueError(f"Group {group_value!r} does not exist; cannot create user")
            group_value = group.id
        if household_value is None or not isinstance(household_value, UUID):
            household_query = Household.filter(group_id=_uuid(group_value))
            household_query = (
                household_query.filter(id=_uuid(household_value))
                if household_value and _looks_uuid(household_value)
                else household_query.filter(name=household_value or get_app_settings().DEFAULT_HOUSEHOLD)
            )
            if connection is not None:
                household_query = household_query.using_db(connection)
            household = await household_query.first()
            if household is None:
                raise ValueError(f"Household {household_value!r} does not exist; cannot create user")
            household_value = household.id
        values["group_id"] = _uuid(group_value)
        values["household_id"] = _uuid(household_value)
        values.pop("tokens", None)
        admin = bool(values.get("admin", False))
        if admin:
            values.update(can_manage_household=True, can_manage=True, can_invite=True, can_organize=True, advanced=True)
        values.setdefault("username", values.get("full_name"))
        if connection is None:
            async with in_transaction() as transaction:
                user = await User.create(using_db=transaction, **values)
            self.create_default_profile_image(user.id)
        else:
            user = await User.create(using_db=connection, **values)
        return await serialize_user(user)

    async def update(self, user_id: Any, data: dict[str, Any] | PrivateUser) -> PrivateUser | None:
        values = data.model_dump(exclude_unset=True) if isinstance(data, PrivateUser) else dict(data)
        values.pop("id", None)
        values.pop("group", None)
        values.pop("household", None)
        values.pop("tokens", None)
        allowed = set(User._meta.fields_db_projection) - {"id", "group_id", "household_id", "owned_recipes_id"}
        values = {key: value for key, value in values.items() if key in allowed}
        if "auth_method" in values:
            auth_method = values["auth_method"]
            values["auth_method"] = AuthMethod[auth_method.name]
        async with in_transaction() as connection:
            user = await User.filter(id=_uuid(user_id)).using_db(connection).first()
            if user is None:
                return None
            for key, value in values.items():
                setattr(user, key, value)
            await user.save(using_db=connection, update_fields=list(values))
        return await serialize_user(user)

    async def update_password(self, user_id: Any, password_hash: str) -> PrivateUser | None:
        async with in_transaction() as connection:
            user = await User.filter(id=_uuid(user_id)).using_db(connection).first()
            if user is None:
                return None
            if get_app_settings().IS_DEMO and user.email == get_app_settings()._DEFAULT_EMAIL.strip().lower():
                return await serialize_user(user)
            user.password = password_hash
            user.tokens_valid_after = datetime.now(UTC).replace(microsecond=0)
            await user.save(using_db=connection, update_fields=["password", "tokens_valid_after"])
        return await serialize_user(user)

    async def get_locked_users(self) -> list[PrivateUser]:
        return [await serialize_user(user) for user in await User.filter(locked_at__not_isnull=True)]


class TortoiseAuthRepository:
    """Authentication token accessors scoped to the async application database."""

    users = TortoiseUserRepository()

    async def get_api_token_user(self, token: str, user_id: Any) -> PrivateUser | None:
        api_token = await LongLiveToken.filter(token=token, user_id=_uuid(user_id)).first()
        if api_token is None or api_token.user_id is None:
            return None
        user = await User.filter(id=api_token.user_id).first()
        return await serialize_user(user) if user else None

    async def create_reset_token(self, user_id: Any, token: str) -> None:
        await PasswordResetModel.create(user_id=_uuid(user_id), token=token)

    async def get_reset_token(self, token: str) -> PasswordResetModel | None:
        return await PasswordResetModel.filter(token=token).first()

    async def delete_reset_token(self, token: str) -> None:
        await PasswordResetModel.filter(token=token).delete()

    async def get_invite(self, token: str, *, connection=None) -> GroupInviteToken | None:
        query = GroupInviteToken.filter(token=token)
        if connection is not None:
            query = query.using_db(connection)
        invite = await query.first()
        if invite:
            await invite.fetch_related("group", "household")
        return invite


__all__ = [
    "Group",
    "GroupInviteToken",
    "GroupPreferencesModel",
    "Household",
    "HouseholdPreferencesModel",
    "TortoiseAuthRepository",
    "TortoiseUserRepository",
    "serialize_user",
]
