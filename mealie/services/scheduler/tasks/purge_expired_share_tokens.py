from datetime import UTC, datetime

from mealie.db.models.tortoise_models import RecipeShareTokenModel


async def purge_expired_tokens() -> None:
    current_time = datetime.now(UTC)
    await RecipeShareTokenModel.filter(expires_at__lt=current_time).delete()
