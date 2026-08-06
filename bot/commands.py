"""Standard bot command menu (native Telegram 'Menu' button)."""
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

STANDARD_COMMANDS = [
    BotCommand(command="order", description="📦 Мій заказ"),
    BotCommand(command="status", description="📊 Статус замовлення"),
    BotCommand(command="scan", description="🔍 Сканувати акції"),
    BotCommand(command="reset", description="🔄 Сброс списку замовлення (адмін/власник)"),
    BotCommand(command="debug", description="ℹ️ Статус бота"),
    BotCommand(command="register", description="✅ Зареєструвати групу"),
]


async def set_default_menu(bot: Bot) -> None:
    await bot.set_my_commands(STANDARD_COMMANDS, scope=BotCommandScopeDefault())


async def set_chat_menu(bot: Bot, chat_id: int) -> None:
    await bot.set_my_commands(
        STANDARD_COMMANDS,
        scope=BotCommandScopeChat(chat_id=chat_id),
    )


async def set_manager_menu(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="status", description="📊 Статуси замовлень"),
        ],
        scope=BotCommandScopeDefault(),
    )


WELCOME_TEXT = (
    "🤖 <b>Спільні закупівлі «Сільпо»</b>\n"
    "Тут з'являтимуться товари зі знижкою ≥25% (акція «Гуртом дешевше»).\n\n"
    "📦 <b>Меню:</b>\n"
    "• <b>/order</b> — переглянути весь свій заказ\n"
    "• <b>/status</b> — статус замовлення будинку\n"
    "• <b>/scan</b> — запустити скан угод\n"
    "• <b>/reset</b> — адміністратор або власник скидає список замовлення\n"
    "• <b>/debug</b> — статус бота\n"
    "• <b>/register</b> — зареєструвати цю групу\n\n"
    "Натискай ➕ на постах з угодами, потім ✅ Підтвердити — і товар з'явиться в заказі.\n\n"
    "🔎 <b>Про конфіденційність:</b> я аналізую тон переписки, щоб пости "
    "звучали природно. Зберігаю лише останні повідомлення (~100), старі "
    "видаляються — довго вони не зберігаються."
)
