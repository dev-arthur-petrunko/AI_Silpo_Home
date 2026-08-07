from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from bot.keyboards import deal_keyboard
from bot.texts import format_deal_text
from core.config import Settings
from core.mcp_client import DeliveryContext, Product, SilpoMCPClient
from core.reminders import remind_about_deal
from core.relevance_scorer import pick_products_for_group
from db.models import Deal, DealStatus, Group
from db.session import get_sessionmaker

logger = logging.getLogger(__name__)

OPEN_STATUSES = (
    DealStatus.collecting,
    DealStatus.goal_reached,
    DealStatus.sent_to_manager,
    DealStatus.confirmed,
)


def parse_scan_times(value: str) -> list[tuple[int, int]]:
    """Розбирає '10:00,14:00,16:00' у список (година, хвилина)."""
    times: list[tuple[int, int]] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            hour, minute = (int(x) for x in part.split(":"))
        except (ValueError, TypeError):
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            times.append((hour, minute))
    return sorted(set(times))


def filter_new_deals(
    products: Iterable[Product],
    existing_product_ids: set[str],
    min_discount_percent: float,
    limit: int | None = None,
) -> list[Product]:
    """Wholesale deals worth posting: in stock, discount above threshold,
    not already published in this group. Sorted by discount (desc), then by
    name; capped at `limit`."""
    result: list[Product] = []
    for product in products:
        if product.mcp_id in existing_product_ids:
            continue
        if not product.in_stock:
            continue
        if product.discount_percent < min_discount_percent:
            continue
        result.append(product)
    result.sort(key=lambda p: (-p.discount_percent, p.name))
    if limit is not None:
        result = result[:limit]
    return result


def group_delivery_address(group: Group, settings: Settings) -> str:
    """Адреса доставки групи (місто) або загальна з налаштувань."""
    return (group.delivery_address or "").strip() or settings.delivery_address


async def scan_promotions(bot: Bot, settings: Settings, session=None, group_id: int | None = None) -> dict:
    """Fetch wholesale deals from MCP and post new ones to active groups.

    Groups are grouped by their delivery address: one MCP scan (branch,
    prices, stock) per unique city. When group_id is given, posts only to
    that group (manual /scan in a group). Otherwise posts to every active
    group (scheduled job).

    Returns a stats dict: {"posted": [...], "skipped_dup": n, "below_threshold": n}."""
    stats: dict = {"posted": [], "skipped_dup": 0, "below_threshold": 0}

    import datetime as dt

    deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.deal_default_deadline_days)

    own_session = session is None
    if session is None:
        session = get_sessionmaker()()
    try:
        if group_id is not None:
            group = (
                await session.execute(
                    select(Group).where(Group.id == group_id, Group.is_active.is_(True))
                )
            ).scalar_one_or_none()
            groups = [group] if group is not None else []
            if not groups:
                logger.warning("no active group %s to post to", group_id)
                return stats
        else:
            groups = (
                await session.execute(select(Group).where(Group.is_active.is_(True)))
            ).scalars().all()
            if not groups:
                logger.warning("no active groups to post to")
                return stats

        by_address: dict[str, list[Group]] = {}
        for group in groups:
            address = group_delivery_address(group, settings)
            by_address.setdefault(address, []).append(group)

        ctx_cache: dict[str, DeliveryContext] = {}
        products_cache: dict[str, list[Product]] = {}
        async with SilpoMCPClient(settings) as mcp:
            for address, address_groups in by_address.items():
                if address not in products_cache:
                    try:
                        ctx = await mcp.resolve_delivery_context(address)
                        products = await mcp.get_wholesale_products(ctx)
                    except Exception:
                        logger.exception(
                            "scan failed for city '%s'; skipping its groups", address
                        )
                        continue
                    ctx_cache[address] = ctx
                    products_cache[address] = products
                    logger.info(
                        "fetched %d wholesale products for '%s'",
                        len(products),
                        address,
                    )
                products = products_cache[address]

                for group in address_groups:
                    cutoff = datetime.now(timezone.utc) - dt.timedelta(days=settings.deal_dup_window_days)
                    existing_ids = set(
                        (
                            await session.execute(
                                select(Deal.mcp_product_id).where(
                                    Deal.group_id == group.id,
                                    Deal.created_at >= cutoff,
                                )
                            )
                        ).scalars().all()
                    )
                    qualified = filter_new_deals(
                        products, existing_ids, settings.min_discount_percent
                    )
                    stats["below_threshold"] += max(
                        0,
                        len([p for p in products if p.mcp_id not in existing_ids]) - len(qualified),
                    )
                    stats["skipped_dup"] += len(existing_ids)

                    # Персональна черга під групу: cold start = топ за знижкою,
                    # далі — релевантність до профілю будинку + explore-слот.
                    ranked = await pick_products_for_group(
                        session,
                        group.id,
                        qualified,
                        daily_limit=settings.max_posts_per_scan,
                        explore_slots=1,
                    )
                    new_deals = ranked

                    for product in new_deals:
                        deal = Deal(
                            group_id=group.id,
                            mcp_product_id=product.mcp_id,
                            product_slug=product.slug,
                            product_name=product.name,
                            image_url=product.image_url,
                            unit_price_retail=product.unit_price_retail,
                            unit_price_wholesale=product.unit_price_wholesale,
                            wholesale_pack_size=product.wholesale_pack_size,
                            savings_per_unit=product.savings_per_unit,
                            weighted=product.weighted,
                            status=DealStatus.collecting,
                            deadline_at=deadline,
                        )
                        session.add(deal)
                        await session.flush()  # deal.id for the keyboard

                        text = format_deal_text(
                            product, collected=0, deadline=deadline, tone_profile=group.tone_profile
                        )
                        keyboard = deal_keyboard(deal.id, deal.wholesale_pack_size, deal.weighted)
                        try:
                            if product.image_url:
                                message = await bot.send_photo(
                                    chat_id=group.telegram_chat_id,
                                    photo=product.image_url,
                                    caption=text,
                                    reply_markup=keyboard,
                                )
                            else:
                                message = await bot.send_message(
                                    chat_id=group.telegram_chat_id,
                                    text=text,
                                    reply_markup=keyboard,
                                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                                )
                        except Exception:
                            logger.exception(
                                "failed to post deal %s to group %s; skipping", product.name, group.telegram_chat_id
                            )
                            session.expunge(deal)
                            continue
                        deal.telegram_message_id = message.message_id
                        stats["posted"].append(f"{group.telegram_chat_id}:{product.name}")
                        logger.info("posted deal #%s '%s' to %s", deal.id, product.name, group.telegram_chat_id)
                        try:
                            reminded = await remind_about_deal(bot, settings, session, group.id, deal)
                            if reminded:
                                logger.info("reminded %d users about deal #%s", reminded, deal.id)
                        except Exception:
                            logger.exception("reminders for deal #%s failed", deal.id)

        await session.commit()
    finally:
        if own_session:
            await session.close()
    return stats


def schedule_jobs(scheduler: AsyncIOScheduler, bot: Bot, settings: Settings) -> None:
    for hour, minute in parse_scan_times(settings.scan_times):
        scheduler.add_job(
            scan_promotions,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=ZoneInfo(settings.scan_timezone),
            ),
            kwargs={"bot": bot, "settings": settings},
            id=f"scan_promotions_{hour:02d}{minute:02d}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    scheduler.add_job(
        refresh_group_tones,
        trigger="interval",
        hours=settings.tone_refresh_hours,
        kwargs={"settings": settings},
        id="refresh_group_tones",
        max_instances=1,
        coalesce=True,
    )


async def refresh_group_tones(settings: Settings, session=None) -> int:
    """Одноразовий розрахунок тону для груп, де набралось >= tone_min_messages."""
    from core.tone_profiler import analyze_group_tone

    own_session = session is None
    if session is None:
        session = get_sessionmaker()()
    try:
        groups = (
            await session.execute(select(Group).where(Group.is_active.is_(True)))
        ).scalars().all()
        done = 0
        for group in groups:
            if group.tone_profile is not None:
                continue
            try:
                if await analyze_group_tone(session, settings, group):
                    done += 1
            except Exception:
                logger.exception("tone analysis failed for group %s", group.id)
        if done:
            logger.info("computed tone profiles for %d groups", done)
        return done
    finally:
        if own_session:
            await session.close()
