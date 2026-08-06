"""Standard bot command menu (native Telegram 'Menu' button)."""
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

STANDARD_COMMANDS = [
    BotCommand(command="order", description="📦 Мій заказ"),
    BotCommand(command="scan", description="🔍 Сканувати акції"),
    BotCommand(command="close", description="🔒 Закрити угоду"),
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


WELCOME_TEXT = (
    "🤖 <b>Спільні закупівлі «Сільпо»</b>\n"
    "Тут з'являтимуться товари зі знижкою ≥50% (акція «Гуртом дешевше»).\n\n"
    "📦 <b>Меню:</b>\n"
    "• <b>/order</b> — переглянути весь свій заказ\n"
    "• <b>/scan</b> — запустити скан угод\n"
    "• <b>/close</b> — адміністратор закриває угоду\n"
    "• <b>/debug</b> — статус бота\n"
    "• <b>/register</b> — зареєструвати цю групу\n\n"
    "Натискай ➕ на постах з угодами, щоб додати товар у заказ.\n\n"
    "🔎 <b>Про конфіденційність:</b> я аналізую тон переписки, щоб пости "
    "звучали природно. Зберігаю лише останні повідомлення (~100), старі "
    "видаляються — довго вони не зберігаються."
)
