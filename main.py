import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.keyboards import parse_deal_join
from core.config import Settings, get_settings
from core.promo_scanner import schedule_jobs, scan_promotions
from db.session import dispose_engine, init_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")


async def main() -> None:
    settings: Settings = get_settings()
    init_engine(settings.database_url)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer("Привіт! Я бот спільних закупівель «Сільпо». Групи сусідів з'являться незабаром.")

    @dp.message(Command("debug"))
    async def cmd_debug(message: Message) -> None:
        await message.answer(
            f"Бот живий.\nЧат: {message.chat.id}\nСканер: {settings.scan_interval_hours} год\n"
            f"Мін. знижка: {settings.min_discount_percent}%"
        )

    @dp.message(Command("scan"))
    async def cmd_scan(message: Message) -> None:
        await message.answer("Сканую оптові акції...")
        try:
            stats = await scan_promotions(bot, settings)
            posted = stats.get("posted", [])
            await message.answer(
                f"Скан завершено.\nНових постів: {len(posted)}\n"
                f"Пропущено (вже опубліковано): {stats.get('skipped_dup', 0)}\n"
                f"Пропущено (нижче порога): {stats.get('below_threshold', 0)}"
            )
        except Exception as exc:
            logger.exception("scan failed")
            await message.answer(f"Помилка сканування: {exc}")

    @dp.callback_query()
    async def on_callback(callback: CallbackQuery) -> None:
        data = callback.data or ""
        if data == "deal:info":
            await callback.answer("Партія — мінімальна кількість для оптової ціни")
            return
        if parse_deal_join(data) is not None:
            await callback.answer("Прийом замовлень — наступний етап розробки")
            return
        await callback.answer()

    scheduler = AsyncIOScheduler(timezone="UTC")
    schedule_jobs(scheduler, bot, settings)
    scheduler.start()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Polling started")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
