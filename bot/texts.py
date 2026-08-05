from datetime import datetime

from core.mcp_client import Product
from core.savings import calc_discount_percent, calc_savings

WHOLESALE_PROMO_LABEL = "Гуртом дешевше"


def _fmt(value: float | int) -> str:
    if isinstance(value, float) and value == int(value):
        return f"{int(value)}"
    return f"{value:.2f}"


def _fmt_qty(value: float | int) -> str:
    """Format an order/pack quantity: '3' for pieces, '0.5' for kg."""
    number = float(value)
    return f"{int(number)}" if number == int(number) else f"{number:g}"


def _pack_unit(weighted: bool) -> str:
    return "кг" if weighted else "шт"


def format_deal_text(
    product: Product,
    collected: int = 0,
    deadline: datetime | None = None,
    deadline_days: int | None = None,
) -> str:
    if deadline is None and deadline_days is not None:
        import datetime as dt

        deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=deadline_days)
    deadline_str = deadline.strftime("%d.%m %H:%M") if deadline else "—"
    unit = _pack_unit(product.weighted)
    pack = _fmt_qty(product.wholesale_pack_size)
    lines = [
        f"🛒 <b>{product.name}</b> — акція «{WHOLESALE_PROMO_LABEL}»!",
        f"Партія: <b>{pack} {unit}</b>",
        f"Ціна в партії: <b>{_fmt(product.unit_price_wholesale)}₴/{unit}</b> "
        f"(роздріб: {_fmt(product.unit_price_retail)}₴/{unit})",
        f"Твоя економія: <b>{_fmt(product.savings_per_unit)}₴</b> на {unit} "
        f"({_fmt(product.discount_percent)}%)",
        "",
        f"Зібрано: <b>{_fmt_qty(collected)}/{pack} {unit}</b>",
        f"Дедлайн збору: {deadline_str}",
    ]
    return "\n".join(lines)


def format_manager_summary() -> str:
    """Placeholder for Phase 5 consolidated order text."""
    return "📦 Зведене замовлення формується у наступній фазі."
