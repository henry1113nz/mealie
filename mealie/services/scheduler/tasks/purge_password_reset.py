import datetime

from mealie.core import root_logger
from mealie.db.models.tortoise_models import PasswordResetModel

logger = root_logger.get_logger()

MAX_DAYS_OLD = 2


async def purge_password_reset_tokens() -> None:
    """Purges all events after x days"""
    logger.debug("purging password reset tokens")
    limit = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=MAX_DAYS_OLD)

    await PasswordResetModel.filter(created_at__lte=limit).delete()
    logger.info("password reset tokens purged")
