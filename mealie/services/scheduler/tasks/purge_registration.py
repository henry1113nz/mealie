import datetime

from mealie.core import root_logger
from mealie.db.db_setup import session_context
from mealie.db.models.household import GroupInviteToken

logger = root_logger.get_logger()

MAX_DAYS_OLD = 4


async def purge_group_registration():
    """Purges all events after x days"""
    logger.debug("purging expired registration tokens")
    limit = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=MAX_DAYS_OLD)

    async with session_context() as session:
        await GroupInviteToken.filter(created_at__lte=limit).using_db(session).delete()

    logger.info("registration token purged")
