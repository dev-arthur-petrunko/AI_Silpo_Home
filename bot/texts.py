from datetime import datetime

from core.mcp_client import Product
from core.savings import calc_discount_percent, calc_savings

WHOLESALE_PROMO_LABEL = "Гуртом дешевше"


def fmt_price(value: float | int) -> str:
    if isinstance(value, float) and value == int(value):
        return f"{int(value)}"
    return f"{value:.2f}"


def fmt_qty(value: float | int) -> str:
    """Format an order/pack quantity: '3' for pieces, '0.5' for kg."""
    number = float(value)
    return f"{int(number)}" if number == int(number) else f"{number:g}"


def pack_unit(weighted: bool) -> str:
    return "кг" if weighted else "шт"


def _deal_lines(
    name: str,
    retail: float,
    wholesale: float,
    pack: float,
    weighted: bool,
    savings: float,
    discount: float,
    collected: float,
    deadline: datetime | None,
) -> str:
    deadline_str = deadline.strftime("%d.%m %H:%M") if deadline else "—"
    unit = pack_unit(weighted)
    pack_s = fmt_qty(pack)
    lines = [
        f"🛒 <b>{name}</b> — акція «{WHOLESALE_PROMO_LABEL}»!",
        f"Партія: <b>{pack_s} {unit}</b>",
        f"Ціна в партії: <b>{fmt_price(wholesale)}₴/{unit}</b> "
        f"(роздріб: {fmt_price(retail)}₴/{unit})",
        f"Твоя економія: <b>{fmt_price(savings)}₴</b> на {unit} "
        f"({fmt_price(discount)}%)",
        "",
        f"Зібрано: <b>{fmt_qty(collected)}/{pack_s} {unit}</b>",
        f"Дедлайн збору: {deadline_str}",
    ]
    return "\n".join(lines)


def format_deal_text(
    product: Product,
    collected: float = 0,
    deadline: datetime | None = None,
    deadline_days: int | None = None,
) -> str:
    if deadline is None and deadline_days is not None:
        import datetime as dt

        deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=deadline_days)
    return _deal_lines(
        product.name,
        product.unit_price_retail,
        product.unit_price_wholesale,
        product.wholesale_pack_size,
        product.weighted,
        product.savings_per_unit,
        product.discount_percent,
        collected,
        deadline,
    )


def format_deal_record(deal, collected: float = 0, deadline: datetime | None = None) -> str:
    """Format a persisted Deal ORM row back into a post caption."""
    import datetime as dt

    if deadline is None:
        deadline = deal.deadline_at
    discount = calc_discount_percent(deal.unit_price_retail, deal.unit_price_wholesale)
    return _deal_lines(
        deal.product_name,
        float(deal.unit_price_retail),
        float(deal.unit_price_wholesale),
        float(deal.wholesale_pack_size),
        deal.weighted,
        float(deal.savings_per_unit),
        discount,
        collected,
        deadline,
    )


def format_order_text(
    sections: list[tuple[str, list[str]]],
    total_cost: float,
    total_savings: float,
) -> str:
    """Order summary: sections of (group_name, formatted lines)."""
    parts = ["📦 <b>Твій заказ</b>", ""]
    for name, lines in sections:
        parts.append(f"<b>{name}</b>")
        parts.extend(lines)
        parts.append("")
    parts.append(f"💰 Разом: <b>{fmt_price(total_cost)}₴</b>")
    parts.append(f"💚 Ти економиш: <b>{fmt_price(total_savings)}₴</b>")
    return "\n".join(parts)


def format_manager_summary() -> str:
    """Placeholder for Phase 5 consolidated order text."""
    return "📦 Зведене замовлення формується у наступній фазі."
