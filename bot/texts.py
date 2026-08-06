from datetime import datetime

from core.mcp_client import Product
from core.savings import calc_discount_percent, calc_savings
from core.tone_profiler import tone_intro, tone_outro

WHOLESALE_PROMO_LABEL = "Гуртом дешевше"

ORDER_STATUS_LABELS: dict[str, str] = {
    "pending": "⏳ Очікує підтвердження менеджера",
    "confirmed": "✅ Підтверджено",
    "packing": "📦 Комплектується",
    "delivering": "🚚 В дорозі",
    "done": "🎉 Виконано",
    "cancelled": "❌ Скасовано",
}


def order_status_text(status: str | None) -> str:
    return ORDER_STATUS_LABELS.get(status or "", "—")


def product_url(slug: str | None) -> str | None:
    if not slug:
        return None
    return f"https://silpo.ua/product/{slug}"


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
    intro: str | None = None,
    outro: str | None = None,
    slug: str | None = None,
) -> str:
    deadline_str = deadline.strftime("%d.%m %H:%M") if deadline else "—"
    unit = pack_unit(weighted)
    pack_s = fmt_qty(pack)
    header = f"🛒 <b>{name}</b> — акція «{WHOLESALE_PROMO_LABEL}»!"
    party = f"📦 Партія: <b>{pack_s} {unit}</b>"
    if weighted:
        r100, w100 = retail / 10, wholesale / 10
        s100 = savings / 10
        lines = [
            header,
            party,
            f"🏷️ В магазині: роздріб <b>{fmt_price(r100)}₴/100г</b>, "
            f"від {pack_s} кг — <b>{fmt_price(w100)}₴/100г</b>",
            f"💰 Твоя економія: <b>{fmt_price(s100)}₴/100г</b> "
            f"({fmt_price(discount)}%)",
            f"⚖️ За кг: <b>{fmt_price(wholesale)}₴/кг</b> замість "
            f"<b>{fmt_price(retail)}₴/кг</b> — вигода <b>{fmt_price(savings)}₴/кг</b>",
        ]
    else:
        lines = [
            header,
            party,
            f"🏷️ Роздріб: <b>{fmt_price(retail)}₴/{unit}</b>",
            f"🎁 Від {pack_s} {unit}: <b>{fmt_price(wholesale)}₴/{unit}</b>",
            f"💰 Твоя економія: <b>{fmt_price(savings)}₴/{unit}</b> "
            f"({fmt_price(discount)}%)",
        ]
    lines += [
        "",
        f"👥 Зібрано: <b>{fmt_qty(collected)}/{pack_s} {unit}</b>",
        f"⏰ Дедлайн збору: {deadline_str}",
    ]
    if slug:
        url = product_url(slug)
        if url:
            lines.append(f"🔗 <a href=\"{url}\">Сторінка товару на silpo.ua</a>")
    if intro:
        lines.insert(0, intro)
    if outro:
        lines.append(outro)
    return "\n".join(lines)


def format_deal_text(
    product: Product,
    collected: float = 0,
    deadline: datetime | None = None,
    deadline_days: int | None = None,
    tone_profile: dict | None = None,
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
        intro=tone_intro(tone_profile),
        outro=tone_outro(tone_profile),
        slug=product.slug,
    )


def format_deal_record(
    deal,
    collected: float = 0,
    pending: list[tuple[str, float]] | None = None,
    deadline: datetime | None = None,
    tone_profile: dict | None = None,
) -> str:
    """Format a persisted Deal ORM row back into a post caption.

    `pending` — список (ім'я, кількість) не підтверджених чернеток, які
    показуються на пості як «очікує підтвердження», але ще не в замовленні.
    """
    import datetime as dt

    if deadline is None:
        deadline = deal.deadline_at
    discount = calc_discount_percent(deal.unit_price_retail, deal.unit_price_wholesale)
    text = _deal_lines(
        deal.product_name,
        float(deal.unit_price_retail),
        float(deal.unit_price_wholesale),
        float(deal.wholesale_pack_size),
        deal.weighted,
        float(deal.savings_per_unit),
        discount,
        collected,
        deadline,
        intro=tone_intro(tone_profile),
        outro=tone_outro(tone_profile),
        slug=getattr(deal, "product_slug", None),
    )
    if pending:
        unit = pack_unit(deal.weighted)
        lines = [f"🔸 Очікує підтвердження:"]
        lines += [
            f"• {who}: <b>+{fmt_qty(qty)} {unit}</b>" for who, qty in pending
        ]
        text += "\n" + "\n".join(lines)
    return text


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
