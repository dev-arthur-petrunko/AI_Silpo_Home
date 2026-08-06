import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bot.commands import WELCOME_TEXT, set_chat_menu, set_default_menu
from bot.keyboards import (
    DEAL_INFO,
    deal_keyboard,
    deal_step,
    parse_deal_dec,
    parse_deal_inc,
    parse_deal_join,
)
from bot.texts import fmt_qty, format_deal_record, pack_unit
from core.config import Settings, get_settings
from core.orders import OPEN_STATUSES, apply_quantity, build_order_summary, close_deal
from core.promo_scanner import schedule_jobs, scan_promotions
from core.tone_profiler import store_message
from db.models import Deal, Group, TelegramUser
from db.session import dispose_engine, get_sessionmaker, init_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")

ACTIVE_MEMBER_STATUSES = {"member", "administrator", "creator"}
DEAL_LOCKS: dict[int, asyncio.Lock] = {}


async def _set_group_ui(bot: Bot, chat_id: int, send_welcome: bool = False) -> None:
    try:
        await set_chat_menu(bot, chat_id)
        if send_welcome:
            await bot.send_message(chat_id, WELCOME_TEXT)
    except TelegramBadRequest as exc:
        logger.warning("could not set menu/welcome for %s: %s", chat_id, exc)


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
                await session.commit()
                await _set_group_ui(bot, event.chat.id, send_welcome=True)
            elif group is not None and group.is_active:
                group.is_active = False
                await session.commit()
                logger.info("bot removed from group %s (%s)", event.chat.id, event.chat.title)
        finally:
            await session.close()

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        session = get_sessionmaker()()
        try:
            user = (
                await session.execute(
                    select(TelegramUser).where(
                        TelegramUser.telegram_user_id == message.from_user.id
                    )
                )
            ).scalar_one_or_none()
            if user is None:
                session.add(
                    TelegramUser(
                        telegram_user_id=message.from_user.id,
                        telegram_username=message.from_user.username,
                        first_name=message.from_user.first_name,
                    )
                )
                await session.commit()
        finally:
            await session.close()
        await message.answer(
            "Привіт! Я бот спільних закупівель «Сільпо». Групи сусідів з'являться незабаром.\n"
            "Після цього я зможу нагадувати тобі в приват про партії, які ти зазвичай замовляєш."
        )

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
            await _set_group_ui(bot, message.chat.id)
            await message.answer(
                f"Групу зареєстровано. Сканер надсилатиме сюди угоди зі знижкою "
                f">= {settings.min_discount_percent:.0f}% (макс {settings.max_posts_per_scan} за скан).\n"
                "Меню команд доступне біля поля вводу (кнопка «Меню»)."
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

    @dp.message(Command("order"))
    async def cmd_order(message: Message) -> None:
        session = get_sessionmaker()()
        try:
            group_db_id: int | None = None
            if message.chat.type in ("group", "supergroup"):
                group = (
                    await session.execute(
                        select(Group).where(Group.telegram_chat_id == message.chat.id)
                    )
                ).scalar_one_or_none()
                group_db_id = group.id if group else None
            text = await build_order_summary(session, message.from_user.id, group_db_id)
        finally:
            await session.close()
        await message.answer(text)

    @dp.message(Command("close"))
    async def cmd_close(message: Message) -> None:
        if message.chat.type not in ("group", "supergroup"):
            await message.answer("Ця команда працює тільки в групах.")
            return
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ("creator", "administrator"):
                await message.answer("Закрити угоду може лише адміністратор групи.")
                return
        except TelegramBadRequest:
            await message.answer("Не вдалось перевірити права. Спробуй ще раз.")
            return

        session = get_sessionmaker()()
        try:
            group = (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == message.chat.id)
                )
            ).scalar_one_or_none()
            if group is None:
                await message.answer("Групу не зареєстровано.")
                return

            args = message.text.split()
            deal: Deal | None = None
            if len(args) > 1:
                try:
                    deal = (
                        await session.execute(select(Deal).where(Deal.id == int(args[1])))
                    ).scalar_one_or_none()
                except ValueError:
                    deal = None
            elif message.reply_to_message is not None:
                deal = (
                    await session.execute(
                        select(Deal).where(
                            Deal.group_id == group.id,
                            Deal.telegram_message_id == message.reply_to_message.message_id,
                        )
                    )
                ).scalar_one_or_none()

            if deal is None:
                await message.answer("Не знайшов угоду. Вкажи id або відповідай на пост з угодою.")
                return
            if deal.group_id != group.id:
                await message.answer("Ця угода з іншої групи.")
                return

            status = await close_deal(session, deal)
            await message.answer(
                f"Угоду «{deal.product_name}» закрито: "
                f"{'замовлено ✅' if status == 'confirmed' else 'завершилась без замовлення ⚪'}"
            )
        finally:
            await session.close()

    @dp.message()
    async def on_group_message(message: Message) -> None:
        """Збираємо повідомлення груп для тону (без команд, ~100 останніх)."""
        if message.chat.type not in ("group", "supergroup"):
            return
        if message.from_user is None or message.from_user.is_bot:
            return
        text = message.text or message.caption or ""
        if not text.strip() or text.lstrip().startswith("/"):
            return
        session = get_sessionmaker()()
        try:
            group = (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == message.chat.id)
                )
            ).scalar_one_or_none()
            if group is None:
                return
            await store_message(session, group.id, message.from_user.id, text, settings.messages_keep)
            await session.commit()
        finally:
            await session.close()

    @dp.callback_query()
    async def on_callback(callback: CallbackQuery) -> None:
        data = callback.data or ""
        if data == DEAL_INFO:
            await callback.answer("Партія — мінімальна кількість для оптової ціни")
            return

        join_id = parse_deal_join(data)
        inc_id = parse_deal_inc(data)
        dec_id = parse_deal_dec(data)
        if join_id is None and inc_id is None and dec_id is None:
            await callback.answer()
            return
        deal_id = join_id or inc_id or dec_id
        if deal_id is None:
            await callback.answer()
            return

        lock = DEAL_LOCKS.setdefault(deal_id, asyncio.Lock())
        async with lock:
            session = get_sessionmaker()()
            try:
                deal = (
                    await session.execute(select(Deal).where(Deal.id == deal_id))
                ).scalar_one_or_none()
                if deal is None:
                    await callback.answer("Угоду не знайдено")
                    return
                if deal.status not in OPEN_STATUSES:
                    await callback.answer("Ця угода вже закрита")
                    return
                group = (
                    await session.execute(select(Group).where(Group.id == deal.group_id))
                ).scalar_one()

                if join_id is not None:
                    delta = deal_step(deal.weighted)
                elif inc_id is not None:
                    delta = deal_step(deal.weighted)
                else:
                    delta = -deal_step(deal.weighted)

                user_total, deal_total, removed = await apply_quantity(
                    session,
                    deal,
                    callback.from_user.id,
                    callback.from_user.username or callback.from_user.first_name,
                    delta,
                )

                text = format_deal_record(deal, collected=deal_total, tone_profile=group.tone_profile)
                keyboard = deal_keyboard(deal.id, deal.wholesale_pack_size, deal.weighted)
                try:
                    if deal.image_url:
                        await bot.edit_message_caption(
                            chat_id=group.telegram_chat_id,
                            message_id=deal.telegram_message_id,
                            caption=text,
                            reply_markup=keyboard,
                        )
                    else:
                        await bot.edit_message_text(
                            chat_id=group.telegram_chat_id,
                            message_id=deal.telegram_message_id,
                            text=text,
                            reply_markup=keyboard,
                        )
                except TelegramBadRequest as exc:
                    logger.warning("could not refresh deal %s post: %s", deal.id, exc)

                unit = pack_unit(deal.weighted)
                if removed:
                    await callback.answer("Ти відмовився від участі")
                else:
                    await callback.answer(f"Ти: {fmt_qty(user_total)} {unit}")
            finally:
                await session.close()

    scheduler = AsyncIOScheduler(timezone="UTC")
    schedule_jobs(scheduler, bot, settings)
    scheduler.start()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await set_default_menu(bot)
        logger.info("Polling started")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
