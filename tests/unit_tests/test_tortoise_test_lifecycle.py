import pytest


@pytest.mark.asyncio
async def test_tortoise_connection_fixture_executes_query(tortoise_connection):
    result = await tortoise_connection.execute_query_dict("SELECT 1 AS value")

    assert result == [{"value": 1}]
