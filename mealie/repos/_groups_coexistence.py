"""Native group deletion on the caller's async transaction."""

from datetime import UTC, datetime
from uuid import UUID

from tortoise import Model
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError

from mealie.db.models.group.ai_providers import AIProvider, AIProviderHeaders, AIProviderParams, AIProviderSettings
from mealie.db.models.group.exports import GroupDataExportsModel
from mealie.db.models.group.group import Group
from mealie.db.models.group.preferences import GroupPreferencesModel
from mealie.db.models.group.report import ReportEntryModel, ReportModel
from mealie.db.models.recipe import (
    Category,
    IngredientFoodModel,
    IngredientUnitModel,
    MultiPurposeLabel,
    RecipeModel,
    RecipeShareTokenModel,
    Tag,
    Tool,
)
from mealie.db.models.server.task import ServerTaskModel
from mealie.db.models.users.users import User


async def delete_group_dependents(group_id: UUID, using_db: BaseDBAsyncClient) -> None:
    """Preserve deletion restrictions and cascades on the caller's transaction."""
    if await User.filter(group_id=group_id).using_db(using_db).exists():
        raise IntegrityError("Cannot delete group with users")

    await ServerTaskModel.filter(group_id=group_id).using_db(using_db).delete()
    reports = await ReportModel.filter(group_id=group_id).using_db(using_db).values_list("id", flat=True)
    await ReportEntryModel.filter(report_id__in=reports).using_db(using_db).delete()
    await ReportModel.filter(group_id=group_id).using_db(using_db).delete()
    settings = await AIProviderSettings.filter(group_id=group_id).using_db(using_db).values_list("id", flat=True)
    providers = await AIProvider.filter(settings_id__in=settings).using_db(using_db).values_list("id", flat=True)
    for field in ("default_provider_id", "audio_provider_id", "image_provider_id"):
        await (
            AIProviderSettings.filter(**{f"{field}__in": providers})
            .using_db(using_db)
            .update(**{field: None, "update_at": datetime.now(UTC)})
        )
    await AIProviderHeaders.filter(provider_id__in=providers).using_db(using_db).delete()
    await AIProviderParams.filter(provider_id__in=providers).using_db(using_db).delete()
    await AIProvider.filter(id__in=providers).using_db(using_db).delete()
    await AIProviderSettings.filter(group_id=group_id).using_db(using_db).delete()
    await GroupPreferencesModel.filter(group_id=group_id).using_db(using_db).delete()
    await GroupDataExportsModel.filter(group_id=group_id).using_db(using_db).delete()

    from mealie.repos._household_coexistence import delete_group_household_dependents

    await delete_group_household_dependents(group_id, using_db)
    group = await Group.filter(id=group_id).using_db(using_db).get()
    await group.categories.clear(using_db=using_db)
    await RecipeShareTokenModel.filter(group_id=group_id).using_db(using_db).delete()
    recipe_models: tuple[type[Model], ...] = (
        RecipeModel,
        IngredientFoodModel,
        IngredientUnitModel,
        MultiPurposeLabel,
        Category,
        Tag,
        Tool,
    )
    for model in recipe_models:
        for entry in await model.filter(group_id=group_id).using_db(using_db):
            await entry.delete(using_db=using_db)
