import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bot.keyboards import parse_deal_join
from core.config import Settings, get_settings
from core.promo_scanner import schedule_jobs, scan_promotions
from db.models import Group
from db.session import dispose_engine, get_sessionmaker, init_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")

ACTIVE_MEMBER_STATUSES = {"member", "administrator", "creator"}


async def main() -> None:
    settings: Settings = get_settings()
    init_engine(settings.database_url)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    @dp.my_chat_member()
    async def on_my_chat_member(event: ChatMemberUpdated) -> None:
        if event.chat.type not in ("group", "supergroup"):
            return
        status = event.new_chat_member.status
        session = get_sessionmaker()()
        try:
            group = (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == event.chat.id)
                )
            ).scalar_one_or_none()
            if status in ACTIVE_MEMBER_STATUSES:
                if group is None:
                    session.add(
                        Group(
                            telegram_chat_id=event.chat.id,
                            house_name=event.chat.title,
                            is_active=True,
                        )
                    )
                    logger.info("bot added to group %s (%s)", event.chat.id, event.chat.title)
                elif not group.is_active:
                    group.is_active = True
                    logger.info("bot re-added to group %s", event.chat.id)
            elif group is not None and group.is_active:
                group.is_active = False
                logger.info("bot removed from group %s (%s)", event.chat.id, event.chat.title)
            await session.commit()
        finally:
            await session.close()

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer("Привіт! Я бот спільних закупівель «Сільпо». Групи сусідів з'являться незабаром.")

    @dp.message(Command("register"))
    async def cmd_register(message: Message) -> None:
        if message.chat.type not in ("group", "supergroup"):
            await message.answer("Ця команда працює тільки в групах.")
            return
        session = get_sessionmaker()()
        try:
            group = (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == message.chat.id)
                )
            ).scalar_one_or_none()
            if group is None:
                session.add(
                    Group(
                        telegram_chat_id=message.chat.id,
                        house_name=message.chat.title,
                        is_active=True,
                    )
                )
            else:
                group.is_active = True
                group.house_name = message.chat.title
            await session.commit()
            await message.answer(
                f"Групу зареєстровано. Сканер надсилатиме сюди угоди зі знижкою "
                f">= {settings.min_discount_percent:.0f}% (макс {settings.max_posts_per_scan} за скан)."
            )
        finally:
            await session.close()

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
            await message.answer(f"Скан завершено. Нових постів: {len(stats.get('posted', []))}")
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
