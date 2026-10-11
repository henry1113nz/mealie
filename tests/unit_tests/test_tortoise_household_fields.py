"""Calendar dates and wall-clock times retain the legacy database formats."""

from datetime import UTC, date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import cast

import pytest
from tortoise import Model

from mealie.core.settings import AppSettings
from mealie.db.models._tortoise_base import CalendarDateField, NaiveTimeField
from mealie.db.models.household.mealplan import GroupMealPlan
from mealie.db.models.household.webhooks import GroupWebhooksModel
from mealie.db.tortoise_config import get_tortoise_config
from mealie.db.tortoise_setup import database_context
from tests.unit_tests.test_tortoise_server import migrated_server_database as migrated_server_database
from tests.unit_tests.test_tortoise_server import server_engine as server_engine
from tests.unit_tests.test_tortoise_server import server_settings as server_settings


@pytest.mark.parametrize("dialect", ["sqlite", "postgres"])
def test_household_calendar_fields_preserve_backend_types(dialect: str) -> None:
    model = cast(
        Model,
        SimpleNamespace(_meta=SimpleNamespace(db=SimpleNamespace(capabilities=SimpleNamespace(dialect=dialect)))),
    )
    date_field = CalendarDateField(null=True)
    time_field = NaiveTimeField(null=True)
    supplied_date = datetime(2026, 5, 6, 23, 30, tzinfo=UTC)
    supplied_time = time(14, 15, 16, 123456, tzinfo=timezone(timedelta(hours=2)))
    expected_date = date(2026, 5, 6)
    expected_time = time(14, 15, 16, 123456)

    assert date_field.get_for_dialect(dialect, "SQL_TYPE") == "DATE"
    assert time_field.get_for_dialect(dialect, "SQL_TYPE") == "TIME"
    assert date_field.to_db_value(supplied_date, model) == (
        expected_date.isoformat() if dialect == "sqlite" else expected_date
    )
    assert time_field.to_db_value(supplied_time, model) == (
        expected_time.isoformat(timespec="microseconds") if dialect == "sqlite" else expected_time
    )
    assert date_field.to_python_value("2026-05-06") == expected_date
    assert date_field.to_python_value(supplied_date) == expected_date
    assert time_field.to_python_value("14:15:16.123456") == expected_time
    assert time_field.to_python_value(supplied_time) == expected_time
    assert date_field.to_db_value(None, model) is None
    assert date_field.to_python_value(None) is None
    assert time_field.to_db_value(None, model) is None
    assert time_field.to_python_value(None) is None


@pytest.mark.asyncio
async def test_native_household_calendar_fields_round_trip_legacy_sqlite(server_settings: AppSettings) -> None:
    async with database_context(get_tortoise_config(server_settings)) as context:
        webhook = await GroupWebhooksModel.create(name="Clock", scheduled_time=time(14, 15, 16, 123456))
        meal = await GroupMealPlan.create(
            date=datetime(2026, 5, 6, 23, 30, tzinfo=UTC), entry_type="dinner", title="Meal", text=""
        )
        assert webhook.scheduled_time == time(14, 15, 16, 123456)
        assert webhook.scheduled_time.tzinfo is None
        assert meal.date == date(2026, 5, 6)
        assert type(meal.date) is date
        rows = await context.db().execute_query_dict(
            "SELECT scheduled_time FROM webhook_urls WHERE id = ?", [webhook.id.hex]
        )
        assert rows[0]["scheduled_time"] == "14:15:16.123456"
        rows = await context.db().execute_query_dict("SELECT date FROM group_meal_plans WHERE id = ?", [meal.id])
        assert rows[0]["date"] == "2026-05-06"
        await webhook.refresh_from_db()
        await meal.refresh_from_db()
        assert webhook.scheduled_time == time(14, 15, 16, 123456)
        assert meal.date == date(2026, 5, 6)
        webhook.scheduled_time = time(6, 7, tzinfo=UTC)
        meal.date = datetime(2026, 5, 7, 23, 30, tzinfo=UTC)
        await webhook.save(update_fields=["scheduled_time", "update_at"])
        await meal.save(update_fields=["date", "update_at"])
        assert webhook.scheduled_time == time(6, 7)
        assert meal.date == date(2026, 5, 7)
        assert (await GroupWebhooksModel.get(id=webhook.id)).scheduled_time == time(6, 7)
        assert (await GroupMealPlan.get(id=meal.id)).date == date(2026, 5, 7)
        webhook.scheduled_time = None
        await webhook.save(update_fields=["scheduled_time", "update_at"])
        assert (await GroupWebhooksModel.get(id=webhook.id)).scheduled_time is None
