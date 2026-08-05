from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from bot.keyboards import deal_step
from bot.texts import fmt_price, fmt_qty, format_order_text, pack_unit
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
    row = await session.execute(
        select(func.coalesce(func.sum(Participant.quantity), 0)).where(
            Participant.deal_id == deal_id
        )
    )
    return float(row.scalar_one() or 0)


async def apply_quantity(
    session: "AsyncSession",
    deal: Deal,
    user_id: int,
    username: str | None,
    delta: float,
) -> tuple[float, float, bool]:
    """Add (delta>0) or subtract (delta<0) a participant's quantity.

    Returns (user_total, deal_total, removed). Commits the transaction.
    """
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
        )
        session.add(part)
        await session.flush()

    new_qty = next_quantity(part.quantity, delta)
    removed = False
    if should_remove(new_qty):
        await session.delete(part)
        removed = True
        user_total = 0.0
    else:
        part.quantity = new_qty
        user_total = new_qty

    total = await deal_total(session, deal.id)
    if (
        not removed
        and deal.status == DealStatus.collecting
        and total >= float(deal.wholesale_pack_size)
    ):
        deal.status = DealStatus.goal_reached
        logger.info("deal %s reached goal (%.3f/%.3f)", deal.id, total, deal.wholesale_pack_size)

    await session.commit()
    return user_total, total, removed


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
