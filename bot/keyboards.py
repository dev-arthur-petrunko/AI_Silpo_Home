from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

DEAL_JOIN_PREFIX = "deal:join:"
DEAL_INC_PREFIX = "deal:inc:"
DEAL_DEC_PREFIX = "deal:dec:"
DEAL_INFO = "deal:info"
DEAL_STOCK_PREFIX = "deal:stock:"
CITY_SETTINGS = "city:settings"
CITY_PICK_PREFIX = "city:pick:"

SUPPORTED_CITIES = [
    "Київ",
    "Львів",
    "Одеса",
    "Харків",
    "Дніпро",
    "Вінниця",
    "Полтава",
    "Черкаси",
    "Івано-Франківськ",
    "Запоріжжя",
    "Хмельницький",
    "Тернопіль",
    "Рівне",
    "Ужгород",
    "Чернівці",
    "Житомир",
    "Луцьк",
]
HOUSE_THINKING = "house:thinking"
HOUSE_CHECKOUT = "house:checkout"
HOUSE_STATUS = "house:status"
MGR_STATUS_PREFIX = "mgr:status:"


def order_keyboard() -> InlineKeyboardMarkup:
    """Кнопки після /order: ще думаємо / оформити для менеджера / статус."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤔 Ще думаємо",
                    callback_data=HOUSE_THINKING,
                ),
                InlineKeyboardButton(
                    text="📦 Оформити замовлення для менеджера",
                    callback_data=HOUSE_CHECKOUT,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статус замовлення",
                    callback_data=HOUSE_STATUS,
                ),
            ],
        ]
    )


def manager_status_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Кнопки зміни статусу замовлення (на повідомленні менеджера)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Підтверджено",
                    callback_data=f"{MGR_STATUS_PREFIX}confirmed:{group_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Скасовано",
                    callback_data=f"{MGR_STATUS_PREFIX}cancelled:{group_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📦 Комплектується",
                    callback_data=f"{MGR_STATUS_PREFIX}packing:{group_id}",
                ),
                InlineKeyboardButton(
                    text="🚚 В дорозі",
                    callback_data=f"{MGR_STATUS_PREFIX}delivering:{group_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎉 Виконано",
                    callback_data=f"{MGR_STATUS_PREFIX}done:{group_id}",
                ),
            ],
        ]
    )


def parse_manager_status(data: str) -> tuple[str, int] | None:
    """Повертає (status, group_id) з 'mgr:status:<status>:<group_id>' або None."""
    if not data.startswith(MGR_STATUS_PREFIX):
        return None
    rest = data[len(MGR_STATUS_PREFIX):]
    try:
        status, group_id = rest.rsplit(":", 1)
        return status, int(group_id)
    except ValueError:
        return None


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
                    text="✅ Підтвердити",
                    callback_data=f"{DEAL_JOIN_PREFIX}{deal_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔎 Наявність",
                    callback_data=f"{DEAL_STOCK_PREFIX}{deal_id}",
                ),
                InlineKeyboardButton(
                    text=f"📦 Партія: {pack} {unit}",
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


def parse_deal_stock(data: str) -> int | None:
    return _parse_deal_id(data, DEAL_STOCK_PREFIX)


def city_settings_keyboard(current: str | None) -> InlineKeyboardMarkup:
    """Кнопка налаштування міста групи (відкриває вибір міста)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌆 Змінити місто групи",
                    callback_data=CITY_SETTINGS,
                ),
            ],
        ]
    )


def city_picker_keyboard(current: str | None) -> InlineKeyboardMarkup:
    """Сітка міст для одноразового вибору адміністратором."""
    rows = []
    for i in range(0, len(SUPPORTED_CITIES), 3):
        row = [
            InlineKeyboardButton(
                text=("✅ " if city == current else "") + city,
                callback_data=f"{CITY_PICK_PREFIX}{city}",
            )
            for city in SUPPORTED_CITIES[i : i + 3]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_city_pick(data: str) -> str | None:
    if not data.startswith(CITY_PICK_PREFIX):
        return None
    city = data[len(CITY_PICK_PREFIX):]
    return city or None
