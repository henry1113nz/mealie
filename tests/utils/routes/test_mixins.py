import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from tortoise.exceptions import IntegrityError

from mealie.routes._base.mixins import is_unique_violation


def make_postgres_integrity_error(pgcode: str) -> IntegrityError:
    orig = Exception("PostgreSQL constraint violation")
    orig.sqlstate = pgcode
    return IntegrityError(orig)


@patch("mealie.routes._base.mixins.get_app_settings")
@pytest.mark.parametrize(
    ("pgcode", "expected"),
    [
        ("23505", True),  # unique_violation
        ("23503", False),  # foreign_key_violation
    ],
)
def test_is_unique_violation_postgres(mock_settings, pgcode, expected):
    mock_settings.return_value = SimpleNamespace(DB_ENGINE="postgres")

    ex = make_postgres_integrity_error(pgcode)

    assert is_unique_violation(ex) is expected


def make_sqlite_integrity_error(sqlite_errorcode: int) -> IntegrityError:
    orig = sqlite3.IntegrityError()
    orig.sqlite_errorcode = sqlite_errorcode
    return IntegrityError(orig)


@patch("mealie.routes._base.mixins.get_app_settings")
@pytest.mark.parametrize(
    ("sqlite_errorcode", "expected"),
    [
        (sqlite3.SQLITE_CONSTRAINT_UNIQUE, True),
        (sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY, False),
    ],
)
def test_is_unique_violation_sqlite(mock_settings, sqlite_errorcode, expected):
    mock_settings.return_value = SimpleNamespace(DB_ENGINE="sqlite")

    ex = make_sqlite_integrity_error(sqlite_errorcode)

    assert is_unique_violation(ex) is expected
