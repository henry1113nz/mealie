from types import SimpleNamespace
from uuid import UUID

import pytest

from mealie.db.models._tortoise_base import UUIDField


@pytest.mark.parametrize("dialect", ["sqlite", "postgres"])
def test_bulk_uuid_update_uses_bound_model_when_instance_is_absent(dialect: str) -> None:
    field = UUIDField()
    field.model = SimpleNamespace(
        _meta=SimpleNamespace(db=SimpleNamespace(capabilities=SimpleNamespace(dialect=dialect)))
    )
    identifier = UUID("193984d6-e8c2-429a-bb6c-19d4a6b728fc")
    expected = identifier.hex if dialect == "sqlite" else str(identifier)
    assert field.to_db_value(identifier, None) == expected
    assert field.to_db_value(str(identifier), None) == expected
    assert field.to_db_value(None, None) is None
