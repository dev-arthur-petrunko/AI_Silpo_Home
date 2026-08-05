from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

DEAL_JOIN_PREFIX = "deal:join:"


def deal_keyboard(deal_id: int, pack_size: float, weighted: bool = False) -> InlineKeyboardMarkup:
    unit = "кг" if weighted else "шт"
    pack = f"{int(pack_size)}" if float(pack_size) == int(pack_size) else f"{pack_size:g}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Приєднатись",
                    callback_data=f"{DEAL_JOIN_PREFIX}{deal_id}",
                ),
                InlineKeyboardButton(
                    text=f"Партія: {pack} {unit}",
                    callback_data="deal:info",
                ),
            ]
        ]
    )


def parse_deal_join(data: str) -> int | None:
    if not data.startswith(DEAL_JOIN_PREFIX):
        return None
    try:
        return int(data[len(DEAL_JOIN_PREFIX):])
    except ValueError:
        return None
