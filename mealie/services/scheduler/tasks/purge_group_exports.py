import datetime
from pathlib import Path

from mealie.core import root_logger
from mealie.core.config import get_app_dirs
from mealie.db.db_setup import session_context
from mealie.db.models.group.exports import GroupDataExportsModel

ONE_DAY_AS_MINUTES = 1440


async def purge_group_data_exports(max_minutes_old=ONE_DAY_AS_MINUTES):
    """Purges all group exports after x days"""
    logger = root_logger.get_logger()

    logger.debug("purging group data exports")
    limit = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=max_minutes_old)

    async with session_context() as session:
        candidates = await GroupDataExportsModel.all().using_db(session)
        results = []
        for candidate in candidates:
            expires = datetime.datetime.fromisoformat(candidate.expires)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=datetime.UTC)
            if expires <= limit:
                results.append(candidate)
        for result in results:
            await result.delete(using_db=session)
            Path(result.path).unlink(missing_ok=True)
        logger.info(f"finished purging group data exports. {len(results)} exports removed from group data")


def purge_excess_files() -> None:
    """Purges all files in the uploads directory that are older than 2 days"""
    directories = get_app_dirs()
    logger = root_logger.get_logger()

    limit = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=ONE_DAY_AS_MINUTES * 2)

    for file in directories.GROUPS_DIR.glob("**/export/*.zip"):
        if file.stat().st_mtime < limit.timestamp():
            file.unlink()
            logger.debug(f"excess group file removed '{file}'")

    logger.info("finished purging excess files")
