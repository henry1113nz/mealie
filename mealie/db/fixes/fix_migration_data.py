from slugify import slugify
from tortoise.backends.base.client import BaseDBAsyncClient

from mealie.core import root_logger
from mealie.db.models.group.group import Group
from mealie.db.models.household.mealplan import GroupMealPlan
from mealie.db.models.household.shopping_list import ShoppingList, ShoppingListMultiPurposeLabel
from mealie.db.models.recipe.comment import RecipeComment
from mealie.db.models.recipe.ingredient import IngredientFoodModel, IngredientUnitModel, RecipeIngredientModel
from mealie.db.models.recipe.labels import MultiPurposeLabel
from mealie.db.models.recipe.recipe import RecipeModel
from mealie.db.models.recipe.recipe_timeline import RecipeTimelineEvent
from mealie.db.models.users.password_reset import PasswordResetModel
from mealie.db.models.users.users import LongLiveToken, User

logger = root_logger.get_logger("init_db")


async def fix_dangling_refs(session: BaseDBAsyncClient) -> None:
    users = await User.all().using_db(session)
    for group in await Group.all().using_db(session):
        members = [user for user in users if user.group_id == group.id]
        if not members:
            continue
        default_user = next((user for user in members if user.admin), members[0])
        for model in (GroupMealPlan, RecipeModel, ShoppingList):
            count = (
                await model.filter(group_id=group.id)
                .exclude(user_id__in=[user.id for user in members])
                .using_db(session)
                .update(user_id=default_user.id)
            )
            if count:
                logger.info(f"Reassigned {count} rows in {model._meta.db_table} to user {default_user.id}")
    for orphan_model in (LongLiveToken, PasswordResetModel, RecipeComment, RecipeTimelineEvent):
        count = await orphan_model.exclude(user_id__in=[user.id for user in users]).using_db(session).delete()
        if count:
            logger.info(f"Deleted {count} rows in {orphan_model._meta.db_table} with invalid user ids")


async def fix_recipe_normalized_search_properties(session: BaseDBAsyncClient) -> None:
    for model, names in [(RecipeModel, ("name", "description")), (RecipeIngredientModel, ("note", "original_text"))]:
        for row in await model.all().using_db(session):
            changed = False
            for name in names:
                value = getattr(row, name)
                if value and not getattr(row, name + "_normalized"):
                    setattr(row, name + "_normalized", model.normalize(value))
                    changed = True
            if changed:
                await row.save(using_db=session)


async def fix_shopping_list_label_settings(session: BaseDBAsyncClient) -> None:
    labels = await MultiPurposeLabel.all().using_db(session)
    for shopping_list in await ShoppingList.all().using_db(session).prefetch_related("label_settings"):
        missing = {label.id: label for label in labels if label.group_id == shopping_list.group_id}
        current = list(shopping_list.label_settings)
        for setting in current:
            if not missing.pop(setting.label_id, None):
                await setting.delete(using_db=session)
        for index, label in enumerate(missing.values(), start=len(current)):
            await ShoppingListMultiPurposeLabel.create(
                shopping_list_id=shopping_list.id, label_id=label.id, position=index, using_db=session
            )


async def fix_group_slugs(session: BaseDBAsyncClient) -> None:
    groups = await Group.all().using_db(session)
    seen = {group.slug for group in groups if group.slug}
    for group in groups:
        if group.slug:
            continue
        name = group.name
        attempt = 0
        while slugify(name) in seen:
            attempt += 1
            name = f"{group.name} ({attempt})"
        group.name, group.slug = name, slugify(name)
        seen.add(group.slug)
        await group.save(using_db=session)


async def fix_normalized_unit_and_food_names(session: BaseDBAsyncClient) -> None:
    for model, names in [(IngredientUnitModel, ("name", "abbreviation")), (IngredientFoodModel, ("name",))]:
        for row in await model.all().using_db(session):
            changed = False
            for name in names:
                value = getattr(row, name)
                if value and not getattr(row, name + "_normalized"):
                    setattr(row, name + "_normalized", model.normalize(value))
                    changed = True
            if changed:
                await row.save(using_db=session)


async def fix_migration_data(session: BaseDBAsyncClient) -> None:
    logger.info("Checking for migration data fixes")
    await fix_dangling_refs(session)
    await fix_recipe_normalized_search_properties(session)
    await fix_shopping_list_label_settings(session)
    await fix_group_slugs(session)
    await fix_normalized_unit_and_food_names(session)
