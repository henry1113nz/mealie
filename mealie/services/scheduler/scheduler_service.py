import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from mealie.core import root_logger
from mealie.core.config import get_app_settings
from mealie.services.scheduler.runner import repeat_every, stop_repeating_tasks

from .scheduler_registry import SchedulerRegistry

logger = root_logger.get_logger()

CWD = Path(__file__).parent

MINUTES_DAY = 1440
MINUTES_5 = 5
MINUTES_HOUR = 60


class SchedulerService:
    _daily_task: asyncio.Task[None] | None = None

    @staticmethod
    async def start():
        await run_minutely()
        await run_hourly()

        # Wait to trigger our daily run until our given "daily time", so having asyncio handle it.
        SchedulerService._daily_task = asyncio.create_task(schedule_daily())

    @staticmethod
    async def stop() -> None:
        if SchedulerService._daily_task is not None:
            SchedulerService._daily_task.cancel()
            await asyncio.gather(SchedulerService._daily_task, return_exceptions=True)
            SchedulerService._daily_task = None
        await stop_repeating_tasks()


async def schedule_daily():
    now = datetime.now(UTC)
    daily_schedule_time = get_app_settings().DAILY_SCHEDULE_TIME_UTC
    logger.debug(f"Current time is {now} and DAILY_SCHEDULE_TIME (in UTC) is {daily_schedule_time}")

    next_schedule = now.replace(
        hour=daily_schedule_time.hour, minute=daily_schedule_time.minute, second=0, microsecond=0
    )
    delta = next_schedule - now
    if delta < timedelta(0):
        next_schedule = next_schedule + timedelta(days=1)
        delta = next_schedule - now

    hours_until, seconds_reminder = divmod(delta.total_seconds(), 3600)
    minutes_until, seconds_reminder = divmod(seconds_reminder, 60)
    seconds_until = round(seconds_reminder)
    logger.debug("Time left: %02d:%02d:%02d", hours_until, minutes_until, seconds_until)

    target_time = next_schedule.replace(microsecond=0, second=0)
    logger.info("Daily tasks scheduled for %s", str(target_time))

    wait_seconds = delta.total_seconds()
    await asyncio.sleep(wait_seconds)
    await run_daily()


async def _scheduled_task_wrapper(callable):
    try:
        if inspect.iscoroutinefunction(callable):
            await callable()
        else:
            await run_in_threadpool(callable)
    except Exception as e:
        logger.error("Error in scheduled task func='%s': exception='%s'", callable.__name__, e)


@repeat_every(minutes=MINUTES_DAY, wait_first=False, logger=logger)
async def run_daily():
    logger.debug("Running daily callbacks")
    for func in SchedulerRegistry._daily:
        await _scheduled_task_wrapper(func)


@repeat_every(minutes=MINUTES_HOUR, wait_first=True, logger=logger)
async def run_hourly():
    logger.debug("Running hourly callbacks")
    for func in SchedulerRegistry._hourly:
        await _scheduled_task_wrapper(func)


@repeat_every(minutes=MINUTES_5, wait_first=True, logger=logger)
async def run_minutely():
    logger.debug("Running minutely callbacks")
    for func in SchedulerRegistry._minutely:
        await _scheduled_task_wrapper(func)
