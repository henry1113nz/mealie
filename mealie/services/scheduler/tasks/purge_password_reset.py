import datetime

from mealie.core import root_logger
from mealie.db.db_setup import session_context
from mealie.db.models.users.password_reset import PasswordResetModel

logger = root_logger.get_logger()

MAX_DAYS_OLD = 2


async def purge_password_reset_tokens():
    """Purges all events after x days"""
    logger.debug("purging password reset tokens")
    limit = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=MAX_DAYS_OLD)

    async with session_context() as session:
        await PasswordResetModel.filter(created_at__lte=limit).using_db(session).delete()
