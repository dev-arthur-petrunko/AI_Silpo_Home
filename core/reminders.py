"""Предиктивні нагадування.

На основі частоти минулих приєднань користувача в категорії товару бот пише
в приват: "ти зазвичай береш масло раз на місяць, зараз якраз збирається
партія — приєднатись?". Частота рахується з історії Participant, текст
генерує LLM (Groq), з шаблонним fallback без мережі.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from statistics import mean
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select

from core.config import Settings
from core.llm import LLMError, llm_text
from core.relevance_scorer import categorize_product
from db.models import Deal, Participant, TelegramUser

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REMINDER_SYSTEM = (
    "Ти — особистий асистент спільних закупівель продуктів. Пишеш дуже короткі "
    "особисті повідомлення сусідам українською. Максимум 2 речення, дружньо, "
    "без канцеляриту, з прямою пропозицією натиснути кнопку приєднатись. "
    "Без привітань, без емодзі-спаму (максимум 1 емодзі)."
)


def frequency_label(join_dates: list[datetime]) -> str | None:
    """Людський опис частоти приєднань: 'раз на місяць', 'раз на тиждень'...

    Рахує середній інтервал між сусідніми приєднаннями. Якщо приєднань менше
    двох — повертає None (частоти ще немає).
    """
    dates = sorted(d for d in join_dates if d is not None)
    if len(dates) < 2:
        return None
    intervals = [
        (dates[i] - dates[i - 1]).total_seconds() / 86400.0
        for i in range(1, len(dates))
        if dates[i] > dates[i - 1]
    ]
    if not intervals:
        return None
    avg_days = mean(intervals)
    if avg_days < 7:
        return "майже щотижня"
    if avg_days < 14:
        return "раз на один-два тижні"
    if avg_days < 30:
        return "раз на місяць"
    if avg_days < 60:
        return "раз на два місяці"
    if avg_days < 180:
        return "раз на кілька місяців"
    return "досить рідко"


async def user_category_joins(
    session: "AsyncSession", group_id: int, user_id: int
) -> dict[str, list[datetime]]:
    """Історія приєднань користувача в групі, згрупована за категорією товару."""
    rows = (
        await session.execute(
            select(Deal.product_name, Participant.created_at)
            .join(Participant, Participant.deal_id == Deal.id)
            .where(Deal.group_id == group_id, Participant.telegram_user_id == user_id)
        )
    ).all()
    by_category: dict[str, list[datetime]] = {}
    for product_name, created_at in rows:
        cat = categorize_product(product_name)
        by_category.setdefault(cat, []).append(created_at)
    return by_category


async def reminder_candidates(
    session: "AsyncSession",
    settings: Settings,
    group_id: int,
    deal_id: int,
    product_name: str,
    max_users: int = 3,
) -> list[tuple[TelegramUser, str, str | None]]:
    """Сусіди, яким варто нагадати про нову партію.

    Умови: користувач натискав /start (є в users), раніше приєднувався в цій
    категорії в цій групі, не учасник цієї угоди, не нагадували щойно.
    Повертає [(TelegramUser, category, frequency_label), ...].
    """
    if not settings.reminders_enabled:
        return []
    category = categorize_product(product_name)

    existing_participants = (
        await session.execute(
            select(Participant.telegram_user_id).where(
                Participant.deal_id == deal_id,
                Participant.confirmed.is_(True),
            )
        )
    ).scalars().all()
    existing = set(existing_participants)

    users = (await session.execute(select(TelegramUser))).scalars().all()
    now = datetime.now(timezone.utc)
    min_interval = settings.reminder_min_interval_days

    scored: list[tuple[int, datetime | None, TelegramUser, str, str | None]] = []
    for user in users:
        if user.telegram_user_id in existing:
            continue
        if user.last_reminder_at is not None:
            last_reminder = user.last_reminder_at
            if last_reminder.tzinfo is None:
                last_reminder = last_reminder.replace(tzinfo=timezone.utc)
            age_days = (now - last_reminder).total_seconds() / 86400.0
            if age_days < min_interval:
                continue
        dates = await user_category_joins(session, group_id, user.telegram_user_id)
        cat_dates = dates.get(category, [])
        if not cat_dates:
            continue
        label = frequency_label(cat_dates)
        last_join = max(cat_dates)
        scored.append((len(cat_dates), last_join, user, category, label))

    scored.sort(key=lambda item: (-item[0], -item[1].timestamp()))
    return [
        (user, cat, label)
        for _count, _last, user, cat, label in scored[:max_users]
    ]


async def build_reminder_text(
    settings: Settings, product_name: str, category: str, frequency: str | None
) -> str:
    """Текст нагадування. LLM з шаблонним fallback."""
    user_msg = (
        f"Товар, який скоро збирається в партію: «{product_name}» (категорія «{category}»). "
        f"Цей сусід раніше брав товари цієї категорії {frequency or 'інколи'}. "
        "Напиши коротке особисте нагадування з пропозицією приєднатись до партії."
    )
    try:
        text = await llm_text(settings, system=REMINDER_SYSTEM, user=user_msg, temperature=0.7, max_tokens=200)
        return text[:600]
    except LLMError as exc:
        logger.warning("reminder LLM failed, using template: %s", exc)
        freq_part = f"Ти зазвичай береш таке {frequency}. " if frequency else "Ти вже брав таке раніше. "
        return (
            f"Привіт! {freq_part}Зараз якраз збирається партія: «{product_name}». "
            "Хочеш приєднатись? 🛒"
        )


async def send_reminder(
    bot: Bot, settings: Settings, session: "AsyncSession", user: TelegramUser, text: str
) -> bool:
    """Надсилає приватне повідомлення і позначає час нагадування."""
    try:
        await bot.send_message(user.telegram_user_id, text)
    except TelegramForbiddenError:
        logger.info("user %s blocked the bot; skip reminders", user.telegram_user_id)
        return False
    except TelegramBadRequest as exc:
        logger.info("cannot message user %s: %s", user.telegram_user_id, exc)
        return False
    user.last_reminder_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def remind_about_deal(
    bot: Bot,
    settings: Settings,
    session: "AsyncSession",
    group_id: int,
    deal: Deal,
    max_users: int | None = None,
) -> int:
    """Розсилає нагадування про нову партію. Повертає кількість надісланих."""
    if not settings.reminders_enabled:
        return 0
    limit = max_users or settings.reminder_max_per_deal
    candidates = await reminder_candidates(
        session, settings, group_id, deal.id, deal.product_name, max_users=limit
    )
    sent = 0
    for user, category, frequency in candidates:
        text = await build_reminder_text(
            settings, deal.product_name, category, frequency
        )
        if await send_reminder(bot, settings, session, user, text):
            sent += 1
    return sent
