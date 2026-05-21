"""Application scheduler wiring."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.db import get_session_factory
from app.jobs.races import run_races_job

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_daily_races_job() -> None:
    settings = get_settings()
    states = settings.scheduler_state_list
    if not states:
        logger.warning("Daily races scheduler skipped: no states configured")
        return

    session_factory = get_session_factory()
    for state in states:
        async with session_factory() as session:
            try:
                result = await run_races_job(session, state=state)
                logger.info("Daily races job finished for %s: %s", state, result)
            except Exception:
                logger.exception("Daily races job failed for %s", state)


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("Content scheduler disabled")
        return
    if _scheduler and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    _scheduler.add_job(
        _run_daily_races_job,
        CronTrigger(hour=settings.scheduler_races_hour, minute=settings.scheduler_races_minute),
        id="daily-races-discovery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "Content scheduler started: daily races at %02d:%02d for states %s",
        settings.scheduler_races_hour,
        settings.scheduler_races_minute,
        ", ".join(settings.scheduler_state_list),
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Content scheduler stopped")
    _scheduler = None
