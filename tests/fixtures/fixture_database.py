from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from mealie.repos.all_repositories import AllRepositories
from tests.utils.async_database import get_repositories
from tests.utils.legacy_database import SessionLocal


@pytest.fixture(scope="module")
def session(api_client: TestClient) -> Generator[sessionmaker[Session]]:
    try:
        sess = SessionLocal()
        yield sess
    finally:
        sess.close()


@pytest.fixture()
def unfiltered_database(session: Session) -> Generator[AllRepositories]:
    yield get_repositories(session, group_id=None, household_id=None)
