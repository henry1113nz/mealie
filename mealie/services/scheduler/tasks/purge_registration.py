import datetime

from mealie.core import root_logger
from mealie.db.models.household import GroupInviteToken

logger = root_logger.get_logger()

MAX_DAYS_OLD = 4


async def purge_group_registration() -> None:
    """Purges all events after x days"""
    logger.debug("purging expired registration tokens")
    limit = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=MAX_DAYS_OLD)

    await GroupInviteToken.filter(created_at__lte=limit).delete()

    logger.info("registration token purged")
