import inspect
import ssl
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import asyncpg
import pytest
from asyncpg import connect_utils

from mealie.db.tortoise_postgres import MealieAsyncpgClient


@pytest.mark.asyncio
async def test_postgres_explicit_credentials_are_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    client = MealieAsyncpgClient(
        connection_name="default",
        host="db.example",
        port=5433,
        user="cook",
        password="p@ss:/%?#[]",
        database="recipes",
    )

    await client.create_connection(with_db=True)

    assert client._pool is create_pool.return_value
    assert create_pool.call_args.args == (None,)
    assert {name: create_pool.call_args.kwargs[name] for name in ("host", "port", "user", "password", "database")} == {
        "host": "db.example",
        "port": 5433,
        "user": "cook",
        "password": "p@ss:/%?#[]",
        "database": "recipes",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dsn", "addresses", "password", "tls_mode", "server_settings"),
    [
        (
            "postgresql://cook:p%40ss%3A%2F%25%3F%23%5B%5D@db.example:5433/recipes"
            "?sslmode=disable&application_name=Mealie%20test",
            [("db.example", 5433)],
            "p@ss:/%?#[]",
            connect_utils.SSLMode.disable,
            {"application_name": "Mealie test"},
        ),
        (
            "postgresql://cook:secret@/recipes?host=%2Frun%2Fpostgresql&port=5437&sslmode=disable",
            ["/run/postgresql/.s.PGSQL.5437"],
            "secret",
            connect_utils.SSLMode.disable,
            {},
        ),
        (
            "postgresql://cook:secret@[::1]:5433/recipes?sslmode=disable",
            [("::1", 5433)],
            "secret",
            connect_utils.SSLMode.disable,
            {},
        ),
        (
            "postgresql://cook:secret@db.example:5433/recipes?sslmode=require",
            [("db.example", 5433)],
            "secret",
            connect_utils.SSLMode.require,
            {},
        ),
    ],
)
async def test_postgres_dsn_reaches_asyncpg_without_default_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    dsn: str,
    addresses: list[tuple[str, int] | str],
    password: str,
    tls_mode: connect_utils.SSLMode,
    server_settings: dict[str, str],
) -> None:
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    # Keep the parser check independent of developer TLS files and settings.
    monkeypatch.setattr(connect_utils, "_dot_postgresql_path", lambda name: tmp_path / name)
    for name in ("PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY", "PGSSLCRL"):
        monkeypatch.delenv(name, raising=False)
    client = MealieAsyncpgClient(connection_name="default", dsn=dsn, minsize=2, maxsize=7)

    await client.create_connection(with_db=True)
    await client.create_connection(with_db=True)

    assert create_pool.await_count == 2
    assert all(call.args == (dsn,) for call in create_pool.call_args_list)
    assert create_pool.call_args.args == (dsn,)
    kwargs = create_pool.call_args.kwargs
    assert not {"dsn", "host", "port", "user", "password", "database"}.intersection(kwargs)
    assert kwargs["min_size"] == 2
    assert kwargs["max_size"] == 7
    assert client._pool is create_pool.return_value
    assert "dsn" not in client.extra
    assert "dsn" not in client._template
    assert "password" not in client._template
    assert dsn not in repr(client._template)

    # Exercise the driver's own URI parser without opening a socket. Parameters
    # added by newer asyncpg versions receive their ordinary None defaults.
    parser = connect_utils._parse_connect_dsn_and_args
    parser_kwargs: dict[str, Any] = dict.fromkeys(inspect.signature(parser).parameters)
    parser_kwargs.update({name: value for name, value in kwargs.items() if name in parser_kwargs})
    parsed_addresses, parameters = parser(
        dsn=dsn, **{name: value for name, value in parser_kwargs.items() if name != "dsn"}
    )
    assert parsed_addresses == addresses
    assert parameters.user == "cook"
    assert parameters.password == password
    assert parameters.database == "recipes"
    assert parameters.sslmode == tls_mode
    assert parameters.server_settings == server_settings
    if tls_mode == connect_utils.SSLMode.require:
        assert isinstance(parameters.ssl, ssl.SSLContext)


@pytest.mark.asyncio
@pytest.mark.parametrize(("value", "timeout"), [("10", 10), ("0", None), ("-1", None), ("", None)])
async def test_postgres_connect_timeout_is_a_client_option(
    monkeypatch: pytest.MonkeyPatch, value: str, timeout: int | None
) -> None:
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    client = MealieAsyncpgClient(
        connection_name="default",
        dsn=f"postgresql://cook:secret@db.example:5433/recipes?sslmode=require&connect_timeout={value}",
    )

    await client.create_connection(with_db=True)

    assert create_pool.call_args.args == ("postgresql://cook:secret@db.example:5433/recipes?sslmode=require",)
    assert create_pool.call_args.kwargs["timeout"] == timeout


@pytest.mark.asyncio
async def test_postgres_invalid_connect_timeout_fails_before_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    create_pool = AsyncMock()
    monkeypatch.setattr(asyncpg, "create_pool", create_pool)
    client = MealieAsyncpgClient(
        connection_name="default", dsn="postgresql://cook:secret@db.example/recipes?connect_timeout=invalid"
    )

    with pytest.raises(ValueError):
        await client.create_connection(with_db=True)

    create_pool.assert_not_called()
