import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.session import async_session_factory
from app.services.card_sync import CardSyncService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_scheduled_card_sync() -> None:
    logger.info("Starting scheduled card sync")
    async with async_session_factory() as session:
        service = CardSyncService()
        try:
            result = await service.sync_cards(session)
            logger.info("Scheduled card sync finished: %s", result.model_dump())
        except Exception:
            logger.exception("Scheduled card sync failed")


def start_scheduler() -> None:
    scheduler.add_job(
        run_scheduled_card_sync,
        trigger=CronTrigger(hour=settings.card_sync_cron_hour, minute=0),
        id="daily_card_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started; daily card sync at hour %d UTC", settings.card_sync_cron_hour)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
