from pathlib import Path

import pytest

from mealie.core.config import get_app_settings
from mealie.core.settings.db_providers import PostgresProvider, SQLiteProvider
from mealie.db.tortoise_config import get_tortoise_config


@pytest.mark.parametrize(
    ("testing", "wal", "expected_pragmas"),
    [
        (False, False, {}),
        (False, True, {"journal_mode": "WAL"}),
        (True, False, {"journal_mode": "MEMORY", "synchronous": "OFF"}),
        (True, True, {"journal_mode": "WAL", "synchronous": "OFF"}),
    ],
)
def test_sqlite_path_and_settings(tmp_path: Path, testing: bool, wal: bool, expected_pragmas: dict[str, str]) -> None:
    provider = SQLiteProvider(data_dir=tmp_path / "spaces and #symbols", prefix="worker_")
    settings = get_app_settings().model_copy(
        update={"DB_PROVIDER": provider, "TESTING": testing, "SQLITE_MIGRATE_JOURNAL_WAL": wal}
    )
    config = get_tortoise_config(settings)
    connection = config["connections"]["default"]

    assert connection["engine"] == "mealie.db.tortoise_sqlite"
    assert connection["credentials"] == {"file_path": str(provider.db_path.absolute()), **expected_pragmas}
    assert config["use_tz"] is True
    assert config["timezone"] == "UTC"


def test_postgres_credentials_preserve_special_characters() -> None:
    provider = PostgresProvider(
        POSTGRES_USER="cook",
        POSTGRES_PASSWORD="p@ss:/%?#[]",
        POSTGRES_SERVER="db.example",
        POSTGRES_PORT="5433",
        POSTGRES_DB="recipes",
        POSTGRES_URL_OVERRIDE=None,
    )
    settings = get_app_settings().model_copy(update={"DB_PROVIDER": provider})
    connection = get_tortoise_config(settings)["connections"]["default"]

    assert connection["engine"] == "mealie.db.tortoise_postgres"
    assert connection["credentials"] == {
        "host": "db.example",
        "port": 5433,
        "user": "cook",
        "password": "p@ss:/%?#[]",
        "database": "recipes",
    }


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgresql://cook:p@ss:word@db.example:5433/recipes?sslmode=require&application_name=mealie",
            "postgresql://cook:p%40ss%3Aword@db.example:5433/recipes?sslmode=require&application_name=mealie",
        ),
        ("postgresql:///recipes?host=/run/postgresql", "postgresql:///recipes?host=/run/postgresql"),
        ("postgresql://cook@[::1]:5433/recipes", "postgresql://cook@[::1]:5433/recipes"),
    ],
)
def test_postgres_override_preserves_socket_tls_and_ipv6(url: str, expected: str) -> None:
    provider = PostgresProvider(POSTGRES_URL_OVERRIDE=url)
    settings = get_app_settings().model_copy(update={"DB_PROVIDER": provider})

    assert get_tortoise_config(settings)["connections"]["default"]["credentials"] == {"dsn": expected}


def test_missing_provider_is_rejected() -> None:
    settings = get_app_settings().model_copy(update={"DB_PROVIDER": None})
    with pytest.raises(ValueError, match="SQLite or PostgreSQL"):
        get_tortoise_config(settings)


def test_config_has_no_domain_models_or_shared_mutable_state(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep the original foundation configuration isolated as domains are added.
    # The production registry is exercised separately by the server model tests.
    monkeypatch.setattr("mealie.db.tortoise_config.TORTOISE_MODEL_MODULES", ("mealie.db.models._tortoise_base",))
    config = get_tortoise_config()
    assert config["apps"] == {
        "models": {"models": ["mealie.db.models._tortoise_base"], "default_connection": "default"}
    }
    config["apps"]["models"]["models"].append("unrelated.module")
    assert get_tortoise_config()["apps"]["models"]["models"] == ["mealie.db.models._tortoise_base"]
