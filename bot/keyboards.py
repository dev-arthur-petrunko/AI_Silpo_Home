from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

DEAL_JOIN_PREFIX = "deal:join:"
DEAL_INC_PREFIX = "deal:inc:"
DEAL_DEC_PREFIX = "deal:dec:"
DEAL_INFO = "deal:info"


def deal_step(weighted: bool) -> float:
    """One increment/decrement step: 0.5 kg for weighted, 1 pc otherwise."""
    return 0.5 if weighted else 1.0


def deal_keyboard(deal_id: int, pack_size: float, weighted: bool = False) -> InlineKeyboardMarkup:
    unit = "кг" if weighted else "шт"
    pack = f"{int(pack_size)}" if float(pack_size) == int(pack_size) else f"{pack_size:g}"
    step = f"{deal_step(weighted):g}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"➕ {step} {unit}",
                    callback_data=f"{DEAL_INC_PREFIX}{deal_id}",
                ),
                InlineKeyboardButton(
                    text=f"➖ {step} {unit}",
                    callback_data=f"{DEAL_DEC_PREFIX}{deal_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Приєднатись",
                    callback_data=f"{DEAL_JOIN_PREFIX}{deal_id}",
                ),
                InlineKeyboardButton(
                    text=f"Партія: {pack} {unit}",
                    callback_data=DEAL_INFO,
                ),
            ],
        ]
    )


def _parse_deal_id(data: str, prefix: str) -> int | None:
    if not data.startswith(prefix):
        return None
    try:
        return int(data[len(prefix):])
    except ValueError:
        return None


def parse_deal_join(data: str) -> int | None:
    return _parse_deal_id(data, DEAL_JOIN_PREFIX)


def parse_deal_inc(data: str) -> int | None:
    return _parse_deal_id(data, DEAL_INC_PREFIX)


def parse_deal_dec(data: str) -> int | None:
    return _parse_deal_id(data, DEAL_DEC_PREFIX)
