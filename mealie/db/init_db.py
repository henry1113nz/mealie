"""Initialize a new Tortoise database and apply the Aerich migration history."""

import asyncio
from pathlib import Path

from aerich import Command
from tortoise.backends.base.client import BaseDBAsyncClient

from mealie.core import root_logger
from mealie.core.config import get_app_settings
from mealie.db.db_setup import close_database, database_config, initialize_database, session_context
from mealie.repos.all_repositories import get_repositories
from mealie.repos.repository_factory import AllRepositories
from mealie.repos.seed.init_users import default_user_init
from mealie.schema.household.household import HouseholdCreate, HouseholdInDB
from mealie.schema.user.user import GroupBase, GroupInDB
from mealie.services.group_services.group_service import GroupService
from mealie.services.household_services.household_service import HouseholdService

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
logger = root_logger.get_logger()


async def init_db(session: BaseDBAsyncClient) -> None:
    settings = get_app_settings()
    instance_repos = get_repositories(session)
    default_group = await default_group_init(instance_repos, settings.DEFAULT_GROUP)
    group_repos = get_repositories(session, group_id=default_group.id, household_id=None)
    default_household = await group_repos.households.get_by_name(settings.DEFAULT_HOUSEHOLD)
    if default_household is None:
        default_household = await default_household_init(group_repos, settings.DEFAULT_HOUSEHOLD)
    household_repos = get_repositories(session, group_id=default_group.id, household_id=default_household.id)
    await default_user_init(household_repos)


async def default_group_init(repos: AllRepositories, name: str) -> GroupInDB:
    logger.info("Generating Default Group and Household")
    return await GroupService.create_group(repos, GroupBase(name=name))


async def default_household_init(repos: AllRepositories, name: str) -> HouseholdInDB:
    logger.info("Generating Default Household")
    return await HouseholdService.create_household(repos, HouseholdCreate(name=name))


async def connect(session: BaseDBAsyncClient) -> bool:
    try:
        await session.execute_query("SELECT 1")
        return True
    except Exception:
        logger.exception("Error connecting to database")
        return False


async def main() -> None:
    await initialize_database()
    async with session_context() as session:
        for attempt in range(10):
            if await connect(session):
                break
            if attempt == 9:
                raise ConnectionError("Database connection failed - exiting application.")
            await asyncio.sleep(1)

    command = Command(database_config(), app="models", location=str(MIGRATIONS_DIR))
    await command.init()
    await command.upgrade()

    async with session_context() as session:
        if get_app_settings().DB_ENGINE == "postgres":
            await session.execute_script("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        repos = get_repositories(session, group_id=None, household_id=None)
        if not await repos.users.count_all():
            logger.info("Database contains no users, initializing...")
            await init_db(session)


async def _cli() -> None:
    try:
        await main()
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(_cli())
