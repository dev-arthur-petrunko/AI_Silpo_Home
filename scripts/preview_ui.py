"""Прев'ю UI вибору кількості (фаза 4).

Надсилає розмічене демо в першу активну групу:
  1) вагова угода (кнопки кг) з лічильником прогресу,
  2) штучна угода (кнопки шт) з лічильником прогресу.

Кнопки неактивні (обробка callback ще не реалізована).
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select

from bot.keyboards import deal_keyboard
from core.config import get_settings
from core.mcp_client import Product
from db.models import Group
from db.session import dispose_engine, get_sessionmaker, init_engine


async def main() -> None:
    settings = get_settings()
    init_engine(settings.database_url)
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        session = get_sessionmaker()()
        group = (await session.execute(select(Group).where(Group.is_active.is_(True)))).scalars().first()
        await session.close()
        if group is None:
            print("no active group")
            return

        chat_id = group.telegram_chat_id
        await bot.send_message(
            chat_id,
            "🔷 <b>ПРЕДПРОСМОТР інтерфейсу</b> (кнопки поки не працюють)\n"
            "Так виглядатимуть пости з кількістю: сир — вибір у кг, товари — у штуках.",
        )

        weighted = Product(
            mcp_id="demo-w", slug="demo", name="Сир Лавка Традицій Чізарня Буррата",
            image_url=None, unit_price_retail=949.0, unit_price_wholesale=65.9,
            wholesale_pack_size=0.5, savings_per_unit=883.1, discount_percent=93.06,
            in_stock=True, weighted=True,
        )
        piece = Product(
            mcp_id="demo-p", slug="demo", name="Снек Oreo молочний",
            image_url=None, unit_price_retail=37.99, unit_price_wholesale=18.99,
            wholesale_pack_size=3, savings_per_unit=19.0, discount_percent=50.01,
            in_stock=True, weighted=False,
        )

        from bot.texts import format_deal_text

        for product, collected in ((weighted, 1.0), (piece, 2)):
            await bot.send_message(
                chat_id,
                format_deal_text(product, collected=collected),
                reply_markup=deal_keyboard(0, product.wholesale_pack_size, product.weighted),
            )
            await asyncio.sleep(1)
        print("preview sent to", chat_id)
    finally:
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
