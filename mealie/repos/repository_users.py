import random
import shutil

from pydantic import UUID4, BaseModel

from mealie.assets import users as users_assets
from mealie.core.config import get_app_settings
from mealie.db.models.users.user_to_recipe import UserToRecipe
from mealie.schema.user.user import PrivateUser, UserRatingOut

from ..db.models.users import User
from .repository_generic import GroupRepositoryGeneric

settings = get_app_settings()


class RepositoryUsers(GroupRepositoryGeneric[PrivateUser, User]):
    async def update_password(self, id, password: str):
        entry = await self._query_one(match_value=id)
        if settings.IS_DEMO:
            user_to_update = await self._to_schema(entry)
            if user_to_update.is_default_user:
                # do not update the default user in demo mode
                return user_to_update

        entry.update_password(password)
        await entry.save(using_db=self.session)

        return await self._to_schema(entry)

    async def create(self, user: PrivateUser | dict):  # type: ignore
        new_user = await super().create(user)

        # Select Random Image
        all_images = [
            users_assets.img_random_1,
            users_assets.img_random_2,
            users_assets.img_random_3,
        ]
        random_image = random.choice(all_images)
        shutil.copy(random_image, new_user.directory() / "profile.webp")

        return new_user

    async def update(self, match_value: str | int | UUID4, new_data: BaseModel | dict) -> PrivateUser:
        if settings.IS_DEMO:
            user_to_update = await self.get_one(match_value)
            if user_to_update and user_to_update.is_default_user:
                # do not update the default user in demo mode
                return user_to_update

        return await super().update(match_value, new_data)

    async def delete(self, value: str | UUID4, match_key: str | None = None) -> PrivateUser:
        if settings.IS_DEMO:
            user_to_delete = await self.get_one(value, match_key)
            if user_to_delete and user_to_delete.is_default_user:
                # do not update the default user in demo mode
                return user_to_delete

        entry = await super().delete(value, match_key)
        # Delete the user's directory
        shutil.rmtree(PrivateUser.get_directory(value))
        return entry

    async def get_by_username(self, username: str) -> PrivateUser | None:
        return await self.get_one(username, key="username")

    async def get_locked_users(self) -> list[PrivateUser]:
        return await self._to_schemas(await self._query().filter(locked_at__isnull=False, **self._filter_builder()))


class RepositoryUserRatings(GroupRepositoryGeneric[UserRatingOut, UserToRecipe]):
    async def get_by_user(self, user_id: UUID4, favorites_only=False) -> list[UserRatingOut]:
        filters = self._filter_builder(user_id=user_id)
        if favorites_only:
            filters["is_favorite"] = True
        return await self._to_schemas(await self._query().filter(**filters))

    async def get_by_recipe(self, recipe_id: UUID4, favorites_only=False) -> list[UserRatingOut]:
        filters = self._filter_builder(recipe_id=recipe_id)
        if favorites_only:
            filters["is_favorite"] = True
        return await self._to_schemas(await self._query().filter(**filters))

    async def get_by_user_and_recipe(self, user_id: UUID4, recipe_id: UUID4) -> UserRatingOut | None:
        entry = await self._query().filter(**self._filter_builder(user_id=user_id, recipe_id=recipe_id)).first()
        return await self._to_schema(entry) if entry is not None else None
