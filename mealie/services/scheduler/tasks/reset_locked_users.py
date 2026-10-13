from datetime import UTC, datetime, timedelta

from mealie.core import root_logger
from mealie.core.config import get_app_settings
from mealie.db.models.tortoise_models import User


async def locked_user_reset() -> int:
    logger = root_logger.get_logger()
    logger.debug("resetting locked users")

    now = datetime.now(UTC).replace(tzinfo=None)
    lockout_window = timedelta(hours=get_app_settings().SECURITY_USER_LOCKOUT_TIME)
    locked_users = await User.filter(locked_at__not_isnull=True)
    unlocked = 0

    for user in locked_users:
        if user.locked_at is not None and user.locked_at + lockout_window <= now:
            user.locked_at = None
            user.login_attemps = 0
            await user.save(update_fields=["locked_at", "login_attemps"])
            unlocked += 1

    logger.debug(f"scheduled task unlocked {unlocked} users in the database")
    logger.info("locked users reset")
    return unlocked
