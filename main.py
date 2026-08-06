import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ChatMemberUpdated, LinkPreviewOptions, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bot.commands import WELCOME_TEXT, set_chat_menu, set_default_menu, set_manager_menu
from bot.keyboards import (
    CITY_SETTINGS,
    DEAL_INFO,
    HOUSE_CHECKOUT,
    HOUSE_STATUS,
    HOUSE_THINKING,
    city_picker_keyboard,
    city_settings_keyboard,
    deal_keyboard,
    deal_step,
    manager_status_keyboard,
    order_keyboard,
    parse_city_pick,
    parse_deal_dec,
    parse_deal_inc,
    parse_deal_join,
    parse_deal_stock,
    parse_manager_status,
)
from bot.texts import fmt_qty, format_deal_record, order_status_text, pack_unit
from core.config import Settings, get_settings
from core.mcp_client import SilpoMCPClient
from core.orders import (
    OPEN_STATUSES,
    build_house_order_summary,
    build_order_summary,
    confirm_draft,
    deal_pending,
    send_house_order_to_manager,
    update_draft,
)
from core.promo_scanner import group_delivery_address, schedule_jobs, scan_promotions
from core.tone_profiler import store_message
from db.models import Deal, DealStatus, Group, Participant, TelegramUser
from db.session import dispose_engine, get_sessionmaker, init_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")

ACTIVE_MEMBER_STATUSES = {"member", "administrator", "creator"}
DEAL_LOCKS: dict[int, asyncio.Lock] = {}
RESET_STATUSES = (
    DealStatus.collecting,
    DealStatus.goal_reached,
    DealStatus.sent_to_manager,
    DealStatus.confirmed,
)

DELIVERY_FORMAT_TEXT = (
    "📍 <b>Оформлення замовлення</b>\n"
    "Напиши одним повідомленням у форматі:\n"
    "<code>Місто | Адреса | Час доставки (з–до) | Телефон отримувача</code>\n"
    "Розділяти можна через <b>|</b> або через <b>кому</b>.\n\n"
    "Приклади:\n"
    "<code>Київ | вул. Хрещатик, 1, кв. 5 | 18:00-21:00 | +380 50 123 45 67</code>\n"
    "<code>Харьков, вул Нескорених 50, кв 6, 18 до 20:00, 0953333902</code>"
)

TIME_RANGE_RE = re.compile(
    r"(?:(?:з|с)\s*)?\d{1,2}(?::\d{2})?\s*(?:[-–—]|до|да)\s*\d{1,2}(?::\d{2}|\s*[-–—]\s*\d{2})?",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{8,14}\d")
PHONE_LABEL_RE = re.compile(r"\b(?:тел\.?|телефон)\s*:?\s*$", re.IGNORECASE)
STREET_RE = re.compile(
    r"(?<![А-Яа-яІіЇїЄєҐґA-Za-z])(?:вул\.?|вулиця|ул\.?|улица|проспект|пр-т|пр\.|б-р|бульвар|наб\.|набережн\w+|шосе|шоссе|провулок|переулок|проїзд|проезд|дорога|вкл\.?)(?=\s|[,;|]|\.|$)",
    re.IGNORECASE,
)
FILLER_RE = re.compile(
    r"(?<![А-Яа-яІіЇїЄєҐґA-Za-z])(?:доставка|адрес\w*|місто|город|телефон|тел\.?)(?=\s|[,;|]|\.|$)",
    re.IGNORECASE,
)
CITY_PREFIX_RE = re.compile(r"^\s*(?:м\.?|г\.?)\s+", re.IGNORECASE)


def _valid_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return 9 <= len(digits) <= 15


def _normalize_time(value: str) -> str:
    """Чистить витягнутий діапазон часу: «да»→«до», прибирає «с/з»,
    «18 до 20-00» → «18-20:00»."""
    value = re.sub(r"\bда\b", "до", value, flags=re.IGNORECASE)
    value = re.sub(r"^\s*(?:з|с)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"(\d{1,2})(?::\d{2})?\s*до\s*(\d{1,2})[-–—](\d{2})",
        r"\1-\2:\3",
        value,
    )
    return re.sub(r"\s+", " ", value).strip()


def _parse_delivery_info(text: str) -> tuple[str, str, str, str] | None:
    """Розбирає 'Місто | Адреса | Час (з–до) | Телефон'.
    Стійкий до вільного вводу: без розділювачів, зі словами «доставка»,
    «телефон», типово «да» замість «до». Спершу витягує телефон і час,
    решту ділить на місто/адресу (за комою або за ключовим словом вулиці)."""
    text = text.strip().strip(" ,;|")
    if not text:
        return None

    phones = list(PHONE_RE.finditer(text))
    if not phones:
        return None
    phone_match = phones[-1]
    phone = phone_match.group(0).strip()
    if not _valid_phone(phone):
        return None
    before = text[: phone_match.start()]
    text = PHONE_LABEL_RE.sub("", before) + " " + text[phone_match.end():]

    time_match = TIME_RANGE_RE.search(text)
    if time_match is None:
        return None
    delivery_time = _normalize_time(time_match.group(0).strip())
    text = text[: time_match.start()] + " " + text[time_match.end():]

    text = FILLER_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;|")
    if not text:
        return None

    chunks = [ch.strip(" ,;|") for ch in re.split(r"[,\|;]", text) if ch.strip(" ,;|")]
    if not chunks:
        return None
    first = chunks[0]
    rest = " ".join(chunks[1:])

    street = STREET_RE.search(first)
    if street:
        city = first[: street.start()].strip(" ,;|") or None
        address = (first[street.start():] + (" " + rest if rest else "")).strip()
    else:
        city = first or None
        address = rest or None

    if city:
        city = CITY_PREFIX_RE.sub("", city).strip() or None
    if not (city and address):
        return None
    return city, address, delivery_time, phone


async def edit_deal_post(
    bot: Bot,
    chat_id: int,
    deal: Deal,
    text: str,
    keyboard=None,
) -> None:
    """Редагує пост угоди (caption або текст), оминаючи ліміти Telegram."""
    kwargs: dict = {
        "chat_id": chat_id,
        "message_id": deal.telegram_message_id,
        "reply_markup": keyboard,
    }
    if deal.image_url:
        kwargs["caption"] = text
    else:
        kwargs["text"] = text
    for attempt in range(3):
        try:
            if deal.image_url:
                await bot.edit_message_caption(**kwargs)
            else:
                await bot.edit_message_text(
                    **kwargs,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            return
        except TelegramRetryAfter as exc:
            await asyncio.sleep(min(exc.retry_after, 10) + attempt)
        except TelegramBadRequest:
            logger.warning("could not edit deal %s post", deal.id)
            return


async def check_deal_stock(settings: Settings, deal: Deal, address: str) -> str:
    """Актуальна наявність товару в магазині через MCP."""
    if not deal.product_slug:
        return f"Не можу перевірити: для «{deal.product_name}» немає slug."
    async with SilpoMCPClient(settings) as mcp:
        ctx = await mcp.resolve_delivery_context(address)
        details = await mcp.get_product_details(ctx, deal.product_slug)
    product = details.get("product") or {}
    stock = product.get("stock") or 0
    available = bool(product.get("available"))
    unit = pack_unit(deal.weighted)
    if available and stock > 0:
        return (
            f"✅ <b>Є в наявності:</b> «{deal.product_name}»\n"
            f"Залишок у магазині: <b>{fmt_qty(stock)} {unit}</b>"
        )
    return f"❌ <b>Розпродано:</b> «{deal.product_name}» зараз недоступний у магазині."


async def reset_house_order(session, group: Group) -> list[Deal]:
    """Скидає замовлення будинку в БД: видаляє всіх учасників, повертає угоди
    у стан collecting, прибирає дані доставки й незавершене оформлення.
    Повертає список угод, чиї пости треба оновити. Комітить транзакцію."""
    deals = (
        (
            await session.execute(
                select(Deal).where(
                    Deal.group_id == group.id,
                    Deal.status.in_(RESET_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    for deal in deals:
        parts = (
            (
                await session.execute(
                    select(Participant).where(Participant.deal_id == deal.id)
                )
            )
            .scalars()
            .all()
        )
        for part in parts:
            await session.delete(part)
        deal.status = DealStatus.collecting
    group.delivery_info = None
    group.checkout_pending = False
    await session.commit()
    return deals


async def _set_group_ui(bot: Bot, chat_id: int, send_welcome: bool = False) -> None:
    try:
        await set_chat_menu(bot, chat_id)
        if send_welcome:
            await bot.send_message(chat_id, WELCOME_TEXT)
    except TelegramBadRequest as exc:
        logger.warning("could not set menu/welcome for %s: %s", chat_id, exc)


async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except TelegramBadRequest:
        return False


def _strip_status_footer(text: str) -> str:
    """Прибирає рядок «📌 Статус: ...» і порожні рядки в кінці тексту."""
    lines = text.split("\n")
    while lines and (not lines[-1].strip() or lines[-1].startswith("📌 Статус:")):
        lines.pop()
    return "\n".join(lines)


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

    @dp.message(Command("settings"))
    async def cmd_settings(message: Message) -> None:
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
                await message.answer("Групу не зареєстровано.")
                return
            current = group.delivery_address or settings.delivery_address
        finally:
            await session.close()
        await message.answer(
            f"🌆 <b>Місто цієї групи:</b> {current}\n"
            "Ціни, наявність і розмір партій рахуємо для цього міста.\n"
            "Змінити місто може адміністратор.",
            reply_markup=city_settings_keyboard(group.delivery_address),
        )

    @dp.message(Command("debug"))
    async def cmd_debug(message: Message) -> None:
        await message.answer(
            f"Бот живий.\nЧат: {message.chat.id}\nСкан: {settings.scan_times} "
            f"({settings.scan_timezone})\nМін. знижка: {settings.min_discount_percent}%"
        )
    @dp.message(Command("scan"))
    async def cmd_scan(message: Message) -> None:
        group_id = None
        if message.chat.type in ("group", "supergroup"):
            session = get_sessionmaker()()
            try:
                group = (
                    await session.execute(
                        select(Group).where(Group.telegram_chat_id == message.chat.id)
                    )
                ).scalar_one_or_none()
            finally:
                await session.close()
            if group is None:
                await message.answer("Групу не зареєстровано. Скан у цій групі неможливий.")
                return
            group_id = group.id
        await message.answer("Сканую оптові акції...")
        try:
            stats = await scan_promotions(bot, settings, group_id=group_id)
            await message.answer(f"Скан завершено. Нових постів: {len(stats.get('posted', []))}")
        except Exception as exc:
            logger.exception("scan failed")
            await message.answer(f"Помилка сканування: {exc}")

    @dp.message(Command("order"))
    async def cmd_order(message: Message) -> None:
        session = get_sessionmaker()()
        try:
            if message.chat.type in ("group", "supergroup"):
                group = (
                    await session.execute(
                        select(Group).where(Group.telegram_chat_id == message.chat.id)
                    )
                ).scalar_one_or_none()
                if group is None:
                    await message.answer("Групу не зареєстровано.")
                    return
                text = await build_house_order_summary(session, group)
                if text is None:
                    text = "Поки що ніхто нічого не замовив. Натискай ➕ на постах з угодами, потім ✅ Підтвердити."
                keyboard = order_keyboard()
            else:
                text = await build_order_summary(session, message.from_user.id)
                keyboard = None
        finally:
            await session.close()
        await message.answer(
            text,
            reply_markup=keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )

    @dp.message(Command("status"))
    async def cmd_status(message: Message) -> None:
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
                await message.answer("Групу не зареєстровано.")
                return
            label = order_status_text(group.order_status)
            await message.answer(f"📊 <b>Статус замовлення будинку:</b> {label}")
        finally:
            await session.close()
    @dp.message(Command("reset"))
    async def cmd_reset(message: Message) -> None:
        if message.chat.type not in ("group", "supergroup"):
            await message.answer("Ця команда працює тільки в групах.")
            return
        try:
            member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ("creator", "administrator"):
                await message.answer("Сброс списку замовлення можуть робити лише адміністратор або власник групи.")
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
            await message.answer(
                "🔄 Починаю сброс списку замовлення...\n"
                "Оновлюю пости угод (може зайняти ~1 хвилину)."
            )
            report = await _reset_order(session, group)
            parts = [
                "✅ <b>Список замовлення скинуто.</b>",
                f"📄 Угод повернуто до збору: <b>{report['deals']}</b>",
                f"📝 Постів оновлено: <b>{report['posts_ok']}</b>",
            ]
            if report["posts_failed"]:
                parts.append(f"⚠️ Не оновлено (помилки): <b>{report['posts_failed']}</b>")
            parts.append("Усі можуть зробити замовлення заново.")
            await message.answer("\n".join(parts))
        finally:
            await session.close()

    @dp.message(F.chat.type == "private")
    async def on_private_forward(message: Message) -> None:
        """Видалення старих повідомлень: перешли його боту, і він видалить оригінал."""
        origin = message.forward_origin
        if origin is None:
            return
        msg_id = getattr(origin, "message_id", None)
        if msg_id is None:
            await message.answer("Не можу визначити, яке повідомлення видалити.")
            return
        origin_chat = getattr(origin, "chat", None)
        if origin_chat is None:
            await message.answer("Не можу видалити це повідомлення (не з чату).")
            return
        chat_id = origin_chat.id
        try:
            if chat_id == settings.manager_chat_id and settings.manager_bot_token:
                del_bot = Bot(token=settings.manager_bot_token)
                try:
                    await del_bot.delete_message(chat_id, msg_id)
                finally:
                    await del_bot.session.close()
            else:
                await bot.delete_message(chat_id, msg_id)
            await message.answer("✅ Старе повідомлення видалено.")
        except Exception:
            logger.exception("failed to delete forwarded message")
            await message.answer(
                "❌ Не вдалось видалити. Бот має бути адміністратором "
                "в групі (для повідомлень ботів — це правило теж діє)."
            )

    @dp.message()
    async def on_group_message(message: Message) -> None:
        """Обробка оформлення замовлення (адмін) + збір повідомлень для тону."""
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

            if group.checkout_pending:
                if not await _is_admin(bot, message.chat.id, message.from_user.id):
                    return
                info = _parse_delivery_info(text)
                if info is None:
                    await message.answer(
                        "Не вдалось розібрати дані. Надішли одним повідомленням через | або кому:\n"
                        "Місто | Адреса | Час доставки (з–до) | Телефон отримувача\n"
                        "Приклад: Київ | вул. Хрещатик, 1, кв. 5 | 18:00-21:00 | +380 50 123 45 67"
                    )
                    return
                city, address, delivery_time, phone = info
                group.delivery_info = {
                    "city": city,
                    "address": address,
                    "delivery_time": delivery_time,
                    "phone": phone,
                }
                group.checkout_pending = False
                await session.commit()

                sent = await send_house_order_to_manager(
                    settings, session, group, delivery_info=group.delivery_info
                )
                if sent:
                    await message.answer(
                        "✅ <b>Замовлення передано менеджеру!</b>\n\n"
                        "📦 Сподіваємось, все буде смачно! 😋\n"
                        "⏳ Менеджер скоро зв'яжеться з вами для підтвердження.\n\n"
                        "💙💛 Дякуємо за замовлення та чудову спільну закупівлю!"
                    )
                    await _reset_order(session, group)
                else:
                    group.checkout_pending = True
                    await session.commit()
                    await message.answer(
                        "Не вдалось передати замовлення менеджеру. Спробуй ще раз."
                    )
                return

            await store_message(session, group.id, message.from_user.id, text, settings.messages_keep)
            await session.commit()
        finally:
            await session.close()

    async def _reset_order(session, group: Group) -> dict:
        """Скидання замовлення будинку (тільки адмін): очищає учасників,
        повертає угоди в збір і прибирає кнопки «передано».
        Повертає звіт: {'deals': int, 'posts_ok': int, 'posts_failed': int}."""
        deals = await reset_house_order(session, group)
        posts_ok = 0
        posts_failed = 0
        for deal in deals:
            if deal.telegram_message_id:
                text = format_deal_record(
                    deal, collected=0, tone_profile=group.tone_profile
                )
                keyboard = deal_keyboard(deal.id, deal.wholesale_pack_size, deal.weighted)
                try:
                    await edit_deal_post(bot, group.telegram_chat_id, deal, text, keyboard)
                    posts_ok += 1
                except Exception:
                    logger.exception("reset: failed to edit post for deal %s", deal.id)
                    posts_failed += 1
                await asyncio.sleep(0.4)
        return {"deals": len(deals), "posts_ok": posts_ok, "posts_failed": posts_failed}

    async def _handle_house_order(callback: CallbackQuery) -> None:
        chat = callback.message.chat
        if chat.type not in ("group", "supergroup"):
            await callback.answer("Це працює тільки в групах")
            return

        data = callback.data or ""
        session = get_sessionmaker()()
        try:
            group = (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == chat.id)
                )
            ).scalar_one_or_none()
            if group is None:
                await callback.answer("Групу не зареєстровано")
                return

            if data == HOUSE_THINKING:
                group.checkout_pending = False
                await session.commit()
                await callback.answer("Ок, чекаємо 😉")
                return

            if data == HOUSE_STATUS:
                label = order_status_text(group.order_status)
                await callback.answer()
                await bot.send_message(
                    chat.id,
                    f"📊 <b>Статус замовлення будинку:</b> {label}",
                )
                return

            if not await _is_admin(bot, chat.id, callback.from_user.id):
                await callback.answer("Оформити замовлення може лише адміністратор")
                return

            text = await build_house_order_summary(session, group)
            if text is None:
                await callback.answer("Поки що немає замовлень")
                return

            group.checkout_pending = True
            await session.commit()
            await bot.send_message(chat.id, DELIVERY_FORMAT_TEXT)
            await callback.answer()
        finally:
            await session.close()

    async def _handle_stock_check(callback: CallbackQuery, deal_id: int) -> None:
        chat = callback.message.chat
        session = get_sessionmaker()()
        try:
            deal = (
                await session.execute(select(Deal).where(Deal.id == deal_id))
            ).scalar_one_or_none()
            group = None
            if deal is not None:
                group = (
                    await session.execute(select(Group).where(Group.id == deal.group_id))
                ).scalar_one_or_none()
        finally:
            await session.close()
        if deal is None or group is None:
            await callback.answer("Угоду не знайдено")
            return
        await callback.answer("Перевіряю наявність у магазині…", show_alert=False)
        try:
            address = group_delivery_address(group, settings)
            text = await check_deal_stock(settings, deal, address)
        except Exception as exc:
            logger.exception("stock check failed for deal %s", deal_id)
            text = f"Не вдалось перевірити наявність: {exc}"
        await bot.send_message(chat.id, text)

    async def _load_group_by_chat(callback: CallbackQuery):
        session = get_sessionmaker()()
        try:
            return (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == callback.message.chat.id)
                )
            ).scalar_one_or_none()
        finally:
            await session.close()

    async def _handle_city_settings(callback: CallbackQuery) -> None:
        chat = callback.message.chat
        if chat.type not in ("group", "supergroup"):
            await callback.answer("Тільки в групах")
            return
        if not await _is_admin(bot, chat.id, callback.from_user.id):
            await callback.answer("Змінити місто може лише адміністратор")
            return
        group = await _load_group_by_chat(callback)
        if group is None:
            await callback.answer("Групу не зареєстровано")
            return
        await callback.answer()
        await callback.message.edit_text(
            "🌆 <b>Оберіть місто групи</b> — ціни, наявність і розмір партій "
            "рахуємо для нього (поки не зміниш):",
            reply_markup=city_picker_keyboard(group.delivery_address),
        )

    async def _handle_city_pick(callback: CallbackQuery, city: str) -> None:
        chat = callback.message.chat
        if chat.type not in ("group", "supergroup"):
            await callback.answer("Тільки в групах")
            return
        if not await _is_admin(bot, chat.id, callback.from_user.id):
            await callback.answer("Змінити місто може лише адміністратор")
            return
        session = get_sessionmaker()()
        try:
            group = (
                await session.execute(
                    select(Group).where(Group.telegram_chat_id == chat.id)
                )
            ).scalar_one_or_none()
            if group is None:
                await callback.answer("Групу не зареєстровано")
                return
            group.delivery_address = city
            await session.commit()
        finally:
            await session.close()
        await callback.answer(f"✅ Місто групи: {city}")
        await callback.message.edit_text(
            f"🌆 <b>Місто групи змінено:</b> {city}\n"
            "Наступні скани та перевірка наявності використовуватимуть ціни "
            "й залишки цього міста.",
            reply_markup=city_settings_keyboard(city),
        )

    @dp.callback_query()
    async def on_callback(callback: CallbackQuery) -> None:
        data = callback.data or ""
        if data == DEAL_INFO:
            await callback.answer("Партія — мінімальна кількість для оптової ціни")
            return

        if data in (HOUSE_THINKING, HOUSE_CHECKOUT, HOUSE_STATUS):
            await _handle_house_order(callback)
            return

        if data == CITY_SETTINGS:
            await _handle_city_settings(callback)
            return

        city = parse_city_pick(data)
        if city is not None:
            await _handle_city_pick(callback, city)
            return

        stock_id = parse_deal_stock(data)
        if stock_id is not None:
            await _handle_stock_check(callback, stock_id)
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
                    confirmed = await confirm_draft(
                        session, deal, callback.from_user.id
                    )
                    if confirmed is None:
                        await callback.answer("Нема що підтверджувати. Спочатку натисни ➕")
                        return
                    qty, collected = confirmed
                else:
                    delta = deal_step(deal.weighted) if inc_id is not None else -deal_step(deal.weighted)
                    user_pending, collected, removed = await update_draft(
                        session,
                        deal,
                        callback.from_user.id,
                        callback.from_user.username or callback.from_user.first_name,
                        delta,
                    )

                pending = await deal_pending(session, deal.id)
                text = format_deal_record(
                    deal,
                    collected=collected,
                    pending=pending,
                    tone_profile=group.tone_profile,
                )
                keyboard = deal_keyboard(deal.id, deal.wholesale_pack_size, deal.weighted)
                await edit_deal_post(bot, group.telegram_chat_id, deal, text, keyboard)

                unit = pack_unit(deal.weighted)
                if join_id is not None:
                    await callback.answer(f"✅ Підтверджено: {fmt_qty(qty)} {unit}")
                elif removed:
                    await callback.answer("Чернетку прибрано")
                else:
                    await callback.answer(
                        f"Ти: {fmt_qty(user_pending)} {unit} (очікує підтвердження)"
                    )
            finally:
                await session.close()

    scheduler = AsyncIOScheduler(timezone="UTC")
    schedule_jobs(scheduler, bot, settings)
    scheduler.start()

    manager_bot: Bot | None = None
    manager_dp: Dispatcher | None = None
    if settings.manager_bot_token:
        manager_bot = Bot(
            token=settings.manager_bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        manager_dp = Dispatcher()
        try:
            await set_manager_menu(manager_bot)
        except Exception:
            logger.warning("could not set manager bot menu")

        @manager_dp.callback_query(F.data.startswith("mgr:status:"))
        async def on_manager_status(callback: CallbackQuery) -> None:
            parsed = parse_manager_status(callback.data or "")
            if parsed is None:
                await callback.answer()
                return
            status, group_id = parsed
            session = get_sessionmaker()()
            try:
                group = (
                    await session.execute(
                        select(Group).where(Group.id == group_id)
                    )
                ).scalar_one_or_none()
                if group is None:
                    await callback.answer("Групу не знайдено")
                    return
                if group.manager_message_id != callback.message.message_id:
                    await callback.answer("Це замовлення вже не актуальне")
                    return
                group.order_status = status
                await session.commit()

                label = order_status_text(status)
                base_text = _strip_status_footer(callback.message.text or "")
                new_text = f"{base_text}\n\n📌 Статус: <b>{label}</b>"
                try:
                    if status in ("done", "cancelled"):
                        await callback.message.edit_text(
                            new_text,
                            reply_markup=None,
                            link_preview_options=LinkPreviewOptions(is_disabled=True),
                        )
                    else:
                        await callback.message.edit_text(
                            new_text,
                            reply_markup=manager_status_keyboard(group_id),
                            link_preview_options=LinkPreviewOptions(is_disabled=True),
                        )
                except TelegramBadRequest:
                    logger.warning(
                        "failed to edit manager order message %s",
                        callback.message.message_id,
                    )

                try:
                    await bot.send_message(
                        group.telegram_chat_id,
                        f"📊 <b>Статус замовлення будинку:</b> {label}",
                    )
                except Exception:
                    logger.exception(
                        "failed to notify group %s about order status",
                        group.telegram_chat_id,
                    )
                await callback.answer(f"Статус: {label}")
            finally:
                await session.close()

        @manager_dp.message(Command("status"))
        async def manager_cmd_status(message: Message) -> None:
            session = get_sessionmaker()()
            try:
                groups = (
                    await session.execute(
                        select(Group).where(Group.is_active.is_(True)).order_by(Group.id)
                    )
                ).scalars().all()
                lines = ["📊 <b>Статуси замовлень:</b>"]
                if not groups:
                    lines.append("Немає активних груп.")
                for g in groups:
                    name = g.house_name or f"Група {g.telegram_chat_id}"
                    lines.append(f"• {name}: <b>{order_status_text(g.order_status)}</b>")
                await message.answer("\n".join(lines))
            finally:
                await session.close()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await set_default_menu(bot)
        await _refresh_group_menus(bot)
        logger.info("Polling started")
        if manager_bot is not None and manager_dp is not None:
            await asyncio.gather(
                dp.start_polling(bot),
                manager_dp.start_polling(manager_bot),
            )
        else:
            await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        if manager_bot is not None:
            await manager_bot.session.close()
        await dispose_engine()


async def _refresh_group_menus(bot: Bot) -> None:
    """Оновлює меню команд у всіх зареєстрованих групах."""
    session = get_sessionmaker()()
    try:
        chat_ids = (
            await session.execute(select(Group.telegram_chat_id))
        ).scalars().all()
    finally:
        await session.close()
    for chat_id in chat_ids:
        await _set_group_ui(bot, chat_id)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
