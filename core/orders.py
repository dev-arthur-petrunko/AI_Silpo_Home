from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from bot.keyboards import deal_step, manager_status_keyboard
from bot.texts import (
    fmt_price,
    fmt_qty,
    format_order_text,
    order_status_text,
    pack_unit,
    product_url,
)
from core.config import Settings
from db.models import Deal, DealStatus, Group, Participant

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

OPEN_STATUSES = (
    DealStatus.collecting,
    DealStatus.goal_reached,
    DealStatus.sent_to_manager,
    DealStatus.confirmed,
)


def next_quantity(current: float, delta: float) -> float:
    """Apply a +/- delta to a participant quantity."""
    return round(float(current) + float(delta), 3)


def should_remove(quantity: float) -> bool:
    return quantity <= 0


async def deal_total(session: "AsyncSession", deal_id: int) -> float:
    """Сума ПІДТВЕРДЖЕНИХ кількостей учасників угоди («Зібрано»)."""
    row = await session.execute(
        select(func.coalesce(func.sum(Participant.quantity), 0)).where(
            Participant.deal_id == deal_id,
            Participant.confirmed.is_(True),
        )
    )
    return float(row.scalar_one() or 0)


async def deal_pending(session: "AsyncSession", deal_id: int) -> list[tuple[str, float]]:
    """Не підтверджені чернетки угоди: список (ім'я, кількість)."""
    parts = (
        (
            await session.execute(
                select(Participant)
                .where(
                    Participant.deal_id == deal_id,
                    Participant.confirmed.is_(False),
                )
                .order_by(Participant.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        (p.telegram_username or f"id{p.telegram_user_id}", float(p.quantity))
        for p in parts
    ]


async def update_draft(
    session: "AsyncSession",
    deal: Deal,
    user_id: int,
    username: str | None,
    delta: float,
) -> tuple[float, float, bool]:
    """Правка чернетки учасника кнопками ➕/➖. У список замовлення не додає —
    це станеться лише після «Підтвердити». Повертає (кількість чернетки
    користувача, зібрано підтверджених, чи чернетку прибрано). Комітить."""
    part = (
        await session.execute(
            select(Participant).where(
                Participant.deal_id == deal.id,
                Participant.telegram_user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    if part is None:
        if delta <= 0:
            return 0.0, await deal_total(session, deal.id), False
        part = Participant(
            deal_id=deal.id,
            telegram_user_id=user_id,
            telegram_username=username,
            quantity=0.0,
            confirmed=False,
        )
        session.add(part)
        await session.flush()

    new_qty = next_quantity(part.quantity, delta)
    removed = False
    if should_remove(new_qty):
        await session.delete(part)
        user_total = 0.0
        removed = True
    else:
        part.quantity = new_qty
        user_total = new_qty

    total = await deal_total(session, deal.id)
    _maybe_mark_reached(deal, total)
    await session.commit()
    return user_total, total, removed


async def confirm_draft(
    session: "AsyncSession",
    deal: Deal,
    user_id: int,
) -> tuple[float, float] | None:
    """«Підтвердити»: додає чернетку користувача до замовлення.
    Повертає (кількість користувача, зібрано підтверджених) або None,
    якщо підтверджувати нема чого. Комітить."""
    part = (
        await session.execute(
            select(Participant).where(
                Participant.deal_id == deal.id,
                Participant.telegram_user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if part is None or part.quantity <= 0 or part.confirmed:
        return None

    part.confirmed = True
    total = await deal_total(session, deal.id)
    _maybe_mark_reached(deal, total)
    await session.commit()
    return float(part.quantity), total


def _maybe_mark_reached(deal: Deal, total: float) -> None:
    if (
        deal.status == DealStatus.collecting
        and total >= float(deal.wholesale_pack_size)
    ):
        deal.status = DealStatus.goal_reached
        logger.info("deal %s reached goal (%.3f/%.3f)", deal.id, total, deal.wholesale_pack_size)


async def build_order_summary(
    session: "AsyncSession", user_id: int, group_id: int | None = None
) -> str:
    """Text of the user's whole order (optionally scoped to one group)."""
    query = (
        select(Participant, Deal, Group)
        .join(Deal, Deal.id == Participant.deal_id)
        .join(Group, Group.id == Deal.group_id)
        .where(
            Participant.telegram_user_id == user_id,
            Participant.confirmed.is_(True),
            Deal.status.in_(OPEN_STATUSES),
        )
        .order_by(Deal.group_id, Deal.id)
    )
    if group_id is not None:
        query = query.where(Deal.group_id == group_id)

    rows = (await session.execute(query)).all()
    if not rows:
        return "У тебе поки що немає замовлень. Обери товар зі знижкою в групі ✅"

    sections: dict[str, list[str]] = {}
    total_cost = 0.0
    total_savings = 0.0
    for participant, deal, group in rows:
        qty = float(participant.quantity)
        retail = float(deal.unit_price_retail)
        wholesale = float(deal.unit_price_wholesale)
        subtotal = round(qty * wholesale, 2)
        savings = round(qty * (retail - wholesale), 2)
        total_cost += subtotal
        total_savings += savings
        unit = pack_unit(deal.weighted)
        lines = sections.setdefault(group.house_name or f"Група {group.telegram_chat_id}", [])
        lines.append(
            f"• {deal.product_name}: <b>{fmt_qty(qty)} {unit}</b> × "
            f"{fmt_price(wholesale)}₴ = <b>{fmt_price(subtotal)}₴</b>"
        )

    return format_order_text(
        list(sections.items()),
        round(total_cost, 2),
        round(total_savings, 2),
    )


async def build_house_order_summary(
    session: "AsyncSession", group: Group, delivery_info: dict | None = None
) -> str | None:
    """Зведення всього будинку: усі відкриті угоди + учасники (хто що взяв)."""
    deals = (
        (
            await session.execute(
                select(Deal).where(
                    Deal.group_id == group.id,
                    Deal.status.in_(OPEN_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    sections: list[str] = []
    total_cost = 0.0
    total_savings = 0.0
    participant_count = 0
    for deal in deals:
        participants = (
            (
                await session.execute(
                    select(Participant)
                    .where(
                        Participant.deal_id == deal.id,
                        Participant.confirmed.is_(True),
                    )
                    .order_by(Participant.quantity.desc())
                )
            )
            .scalars()
            .all()
        )
        if not participants:
            continue
        unit = pack_unit(deal.weighted)
        wholesale = float(deal.unit_price_wholesale)
        retail = float(deal.unit_price_retail)
        title = f"<b>{deal.product_name}</b>"
        url = product_url(deal.product_slug)
        if url:
            title = f"<a href=\"{url}\">{title}</a>"
        lines = [f"📦 {title}"]
        deal_cost = 0.0
        for p in participants:
            qty = float(p.quantity)
            subtotal = round(qty * wholesale, 2)
            deal_cost += subtotal
            total_cost += subtotal
            total_savings += round(qty * (retail - wholesale), 2)
            participant_count += 1
            who = p.telegram_username or f"id{p.telegram_user_id}"
            lines.append(
                f"• {who}: <b>{fmt_qty(qty)} {unit}</b> × {fmt_price(wholesale)}₴ "
                f"= <b>{fmt_price(subtotal)}₴</b>"
            )
        lines.append(f"   Підсумок: <b>{fmt_price(round(deal_cost, 2))}₴</b>")
        sections.append("\n".join(lines))
    if not sections:
        return None

    header = (
        f"🏠 <b>ЗАМОВЛЕННЯ БУДИНКУ</b>\n"
        f"<b>{group.house_name or 'Група'}</b>\n\n"
    )
    if delivery_info:
        header += (
            f"📍 Місто: <b>{delivery_info.get('city') or '—'}</b>\n"
            f"🏠 Адреса: <b>{delivery_info.get('address') or '—'}</b>\n"
            f"🕐 Час доставки: <b>{delivery_info.get('delivery_time') or '—'}</b>\n"
            f"📞 Телефон отримувача: <b>{delivery_info.get('phone') or '—'}</b>\n\n"
        )
    footer = (
        f"💰 Разом: <b>{fmt_price(round(total_cost, 2))}₴</b> "
        f"(позицій: {participant_count})\n"
        f"💚 Економія: <b>{fmt_price(round(total_savings, 2))}₴</b>"
    )
    return header + "\n\n".join(sections) + "\n\n" + footer


async def send_house_order_to_manager(
    settings: Settings, session: "AsyncSession", group: Group, delivery_info: dict | None = None
) -> int | None:
    """Надіслати зведення замовлення будинку в групу менеджера (через бота2).
    Повертає message_id повідомлення або None."""
    if not settings.manager_chat_id or not settings.manager_bot_token:
        logger.info("manager not configured; skip house order send")
        return None

    text = await build_house_order_summary(session, group, delivery_info=delivery_info)
    if not text:
        logger.info("group %s has no open orders; skip manager send", group.id)
        return None

    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from aiogram.types import LinkPreviewOptions

        manager_bot = Bot(
            token=settings.manager_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            message = await manager_bot.send_message(
                settings.manager_chat_id,
                text + f"\n\n📌 Статус: <b>{order_status_text('pending')}</b>",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=manager_status_keyboard(group.id),
            )
            group.manager_message_id = message.message_id
            group.order_status = "pending"
            logger.info(
                "house order for group %s sent to manager chat %s (msg %s)",
                group.id,
                settings.manager_chat_id,
                message.message_id,
            )
            return message.message_id
        finally:
            await manager_bot.session.close()
    except Exception:
        logger.exception("failed to send house order for group %s", group.id)
        return None
