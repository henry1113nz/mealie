"""Aerich migration and default-data initialization on the owning async loop."""

import asyncio
from pathlib import Path

from tortoise import BaseDBAsyncClient
from tortoise.context import get_current_context

from mealie.core import root_logger
from mealie.core.config import get_app_settings
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from mealie.repos.all_repositories import get_repositories
from mealie.repos.repository_factory import AllRepositories
from mealie.repos.seed.init_users import default_user_init
from mealie.schema.household.household import HouseholdCreate, HouseholdInDB
from mealie.schema.user.user import GroupBase, GroupInDB
from mealie.services.group_services.group_service import GroupService
from mealie.services.household_services.household_service import HouseholdService

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
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


async def prepare_database() -> bool:
    """Apply checked-in Aerich migrations using the active database context.

    Aerich's init reuses the initialized Tortoise context. Do not enter Command
    as a context manager here: the application, script, or test owns connections.
    The initial migration supports fresh databases; old Alembic upgrades are not
    part of this schema history.
    """
    from aerich import Command

    connection = get_current_context().db()
    if connection.capabilities.dialect == "sqlite":
        legacy = await connection.execute_query_dict(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
        )
    else:
        legacy = await connection.execute_query_dict(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = 'alembic_version'"
        )
    if legacy:
        raise RuntimeError(
            "This database uses the old Alembic schema. Upgrading it to the Aerich schema is unsupported."
        )
    command = Command(tortoise_config=get_tortoise_config(), app="models", location=str(MIGRATIONS_DIR))
    await command.init()
    migrated = await command.upgrade()
    if migrated:
        logger.info("Applied database migrations: %s", ", ".join(migrated))
    else:
        logger.debug("Database migrations are current.")
    return bool(migrated)


async def initialize_data(run_fixes: bool = False) -> None:
    """Seed a fresh database after migrations, within its existing context."""
    session = get_current_context().db()
    db = get_repositories(session, group_id=None, household_id=None)
    if await db.users.get_all():
        logger.debug("Database exists")
    else:
        logger.info("Database contains no users, initializing...")
        await init_db(session)


async def main() -> None:
    async with database_context():
        await prepare_database()
        await initialize_data()


if __name__ == "__main__":
    asyncio.run(main())
