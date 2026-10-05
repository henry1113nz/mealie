from mealie.db.db_setup import native_connection_config


def test_native_sqlite_url_preserves_absolute_database_path():
    config = native_connection_config("sqlite:////var/lib/mealie/mealie.db")

    assert config["engine"] == "tortoise.backends.sqlite"
    assert config["credentials"]["file_path"] == "/var/lib/mealie/mealie.db"


def test_native_postgres_url_preserves_socket_and_encoded_password():
    config = native_connection_config("postgresql://mealie:p%40ssword@/mealie?host=/run/postgresql")

    assert config["engine"] == "tortoise.backends.asyncpg"
    assert config["credentials"]["host"] == "/run/postgresql"
    assert config["credentials"]["password"] == "p@ssword"
    assert config["credentials"]["database"] == "mealie"


def test_native_postgres_url_translates_connection_options():
    config = native_connection_config("postgresql://mealie@db/mealie?sslmode=verify-full&connect_timeout=15")

    assert config["credentials"]["ssl"] == "verify-full"
    assert config["credentials"]["timeout"] == 15.0
    assert "sslmode" not in config["credentials"]
    assert "connect_timeout" not in config["credentials"]
