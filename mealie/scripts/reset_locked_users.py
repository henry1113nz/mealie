import asyncio

from mealie.core import root_logger
from mealie.db.db_setup import session_context
from mealie.db.tortoise_setup import database_context
from mealie.repos.repository_factory import AllRepositories
from mealie.services.user_services.user_service import UserService


async def main() -> None:
    async with database_context():
        confirmed = input("Are you sure you want to reset all locked users? (y/n) ")

        if confirmed != "y":
            print("aborting")  # noqa
            exit(0)

        logger = root_logger.get_logger()

        with session_context() as session:
            repos = AllRepositories(session, group_id=None, household_id=None)
            user_service = UserService(repos)

            locked_users = await user_service.get_locked_users()

            if not locked_users:
                logger.error("no locked users found")

            for user in locked_users:
                logger.info(f"unlocking user {user.username}")
                await user_service.unlock_user(user)

        input("press enter to exit ")
        exit(0)


if __name__ == "__main__":
    asyncio.run(main())
