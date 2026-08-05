import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import Settings

logger = logging.getLogger(__name__)


async def scan_promotions(bot: Bot, settings: Settings) -> None:
    """Placeholder for Phase 3: fetch wholesale deals from MCP and post to groups."""
    logger.info("scan_promotions job fired (not yet implemented)")


def schedule_jobs(scheduler: AsyncIOScheduler, bot: Bot, settings: Settings) -> None:
    scheduler.add_job(
        scan_promotions,
        trigger="interval",
        hours=settings.scan_interval_hours,
        kwargs={"bot": bot, "settings": settings},
        id="scan_promotions",
        max_instances=1,
        coalesce=True,
    )
