"""Registration-only async group/household bootstrap and user creation."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi import HTTPException, status
from slugify import slugify
from tortoise.expressions import F
from tortoise.transactions import in_transaction

from mealie.core.config import get_app_settings
from mealie.db.tortoise_models import Group, Household, User
from mealie.db.tortoise_models.ingredient import IngredientFood, IngredientUnit
from mealie.db.tortoise_models.remaining import (
    AIProviderSettings,
    GroupInviteToken,
    GroupPreferencesModel,
    HouseholdPreferencesModel,
    MultiPurposeLabel,
)
from mealie.lang.locale_config import resolve_food_plural, resolve_plural
from mealie.repos.tortoise_user import TortoiseUserRepository
from mealie.schema.group.group_preferences import CreateGroupPreferences
from mealie.schema.user.registration import CreateUserRegistration
from mealie.schema.user.user import PrivateUser


class TortoiseRegistrationService:
    def __init__(self, translator) -> None:
        self.t = translator.t
        self.users = TortoiseUserRepository()
        self.settings = get_app_settings()

    async def register_user(self, registration: CreateUserRegistration) -> PrivateUser:
        async with in_transaction() as connection:
            invite = None
            new_group = False
            if registration.group_token:
                # Make the conditional update the transaction's first database write. This
                # serializes redemption on SQLite as well as PostgreSQL and prevents two
                # deferred SQLite transactions from both reading a use before either writes.
                consumed = (
                    await GroupInviteToken.filter(token=registration.group_token, uses_left__gt=0)
                    .using_db(connection)
                    .update(uses_left=F("uses_left") - 1)
                )
                if consumed != 1:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Invalid group token"})
                invite = await GroupInviteToken.filter(token=registration.group_token).using_db(connection).first()
                if invite is None or invite.group_id is None or invite.household_id is None:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Invalid group token"})

            if await User.filter(username=registration.username).using_db(connection).exists():
                raise HTTPException(status.HTTP_409_CONFLICT, {"message": self.t("exceptions.username-conflict-error")})
            if await User.filter(email=registration.email).using_db(connection).exists():
                raise HTTPException(status.HTTP_409_CONFLICT, {"message": self.t("exceptions.email-conflict-error")})

            if registration.group_token:
                if invite is None:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Invalid group token"})
                group = await Group.filter(id=invite.group_id).using_db(connection).first()
                household = (
                    await Household.filter(id=invite.household_id, group_id=invite.group_id)
                    .using_db(connection)
                    .first()
                )
                if group is None or household is None:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Invalid group token"})
            elif registration.group:
                new_group = True
                group, household = await self._create_group_and_household(registration, connection)
            else:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, {"message": "Missing group"})

            user = await self.users.create(
                {
                    "username": registration.username,
                    "full_name": registration.full_name,
                    "email": registration.email,
                    "password": self._hash_password(registration.password),
                    "advanced": registration.advanced,
                    "group_id": group.id,
                    "household_id": household.id,
                    "can_invite": new_group,
                    "can_manage": new_group,
                    "can_manage_household": new_group,
                    "can_organize": new_group,
                },
                connection=connection,
            )

            if invite is not None and invite.uses_left == 0:
                await GroupInviteToken.filter(id=invite.id).using_db(connection).delete()

        if new_group and registration.seed_data:
            await self._seed_group_data(group.id, registration.locale)
        self.users.create_default_profile_image(user.id)
        return user

    async def _create_group_and_household(
        self, registration: CreateUserRegistration, connection
    ) -> tuple[Group, Household]:
        original_name = registration.group or ""
        group = None
        for suffix in range(10):
            name = original_name if suffix == 0 else f"{original_name} ({suffix})"
            try:
                group = await Group.create(using_db=connection, id=uuid4(), name=name, slug=slugify(name))
                break
            except Exception as error:
                if "unique" not in str(error).lower() and "duplicate" not in str(error).lower():
                    raise
        if group is None:
            raise RuntimeError("Unable to create unique group")

        preferences = CreateGroupPreferences(group_id=group.id, private_group=registration.private)
        await GroupPreferencesModel.create(
            using_db=connection, group_id=group.id, **preferences.model_dump(exclude={"group_id"})
        )
        await AIProviderSettings.create(using_db=connection, group_id=group.id)

        household_name = registration.household or self.settings.DEFAULT_HOUSEHOLD
        household = await Household.filter(group_id=group.id, name=household_name).using_db(connection).first()
        if household is None:
            household = await Household.create(
                using_db=connection,
                id=uuid4(),
                group_id=group.id,
                name=household_name,
                slug=slugify(household_name),
            )
            await HouseholdPreferencesModel.create(
                using_db=connection,
                household_id=household.id,
                private_household=registration.private,
                first_day_of_week=0,
                recipe_public=not registration.private,
                recipe_show_nutrition=registration.advanced,
                recipe_show_assets=registration.advanced,
                recipe_landscape_view=False,
                recipe_disable_comments=registration.advanced,
            )
        return group, household

    @staticmethod
    def _hash_password(password: str) -> str:
        from mealie.core.security import hash_password

        return hash_password(password)

    async def _seed_group_data(self, group_id, locale: str) -> None:
        """Insert the existing locale seed data through Tortoise, without legacy repos."""
        from mealie.repos.seed.seeders import IngredientFoodsSeeder

        resources = IngredientFoodsSeeder.resources
        foods_file = resources / "foods" / "locales" / f"{locale}.json"
        units_file = resources / "units" / "locales" / f"{locale}.json"
        foods_file = foods_file if foods_file.exists() else resources / "foods" / "locales" / "en-US.json"
        units_file = units_file if units_file.exists() else resources / "units" / "locales" / "en-US.json"
        food_data = json.loads(foods_file.read_text(encoding="utf-8"))
        source_food_data = json.loads((resources / "foods" / "locales" / "en-US.json").read_text(encoding="utf-8"))
        unit_data = json.loads(units_file.read_text(encoding="utf-8"))
        source_unit_data = json.loads((resources / "units" / "locales" / "en-US.json").read_text(encoding="utf-8"))

        labels: dict[str, MultiPurposeLabel] = {}
        existing_food_names = set(await IngredientFood.filter(group_id=group_id).values_list("name", flat=True))
        existing_unit_names = set(await IngredientUnit.filter(group_id=group_id).values_list("name", flat=True))
        for key, entry in food_data.items():
            label_name = entry["name"]
            label = await MultiPurposeLabel.filter(group_id=group_id, name=label_name).first()
            if label is None:
                label = await MultiPurposeLabel.create(group_id=group_id, name=label_name, color="#959595")
            labels[key] = label
            source_foods = source_food_data.get(key, {}).get("foods", {})
            for food_key, food in entry["foods"].items():
                name = food["name"]
                if name in existing_food_names:
                    continue
                existing_food_names.add(name)
                source = source_foods.get(food_key, food)
                plural = resolve_food_plural(
                    source_singular=source["name"],
                    source_plural=source.get("plural_name"),
                    singular=name,
                    plural=food.get("plural_name"),
                    locale=locale,
                )
                await IngredientFood.create(
                    group_id=group_id, name=name, plural_name=plural, description="", label_id=label.id
                )

        for key, unit in unit_data.items():
            name = unit["name"]
            if name in existing_unit_names:
                continue
            existing_unit_names.add(name)
            source = source_unit_data.get(key, unit)
            await IngredientUnit.create(
                group_id=group_id,
                name=name,
                plural_name=resolve_plural(
                    source_singular=source["name"],
                    source_plural=source.get("plural_name"),
                    singular=name,
                    plural=unit.get("plural_name"),
                ),
                description=unit.get("description", ""),
                abbreviation=unit.get("abbreviation", ""),
                plural_abbreviation=resolve_plural(
                    source_singular=source.get("abbreviation", ""),
                    source_plural=source.get("plural_abbreviation"),
                    singular=unit.get("abbreviation", ""),
                    plural=unit.get("plural_abbreviation"),
                ),
                fraction=True,
            )
