import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.orders import confirm_draft, deal_pending, deal_total, update_draft
from db.base import Base
from db.models import Deal, DealStatus, Group, Participant
from main import RESET_STATUSES


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_draft_confirm_flow():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session:
            group = Group(telegram_chat_id=-100, house_name="Тест")
            session.add(group)
            await session.flush()
            deal = Deal(
                group_id=group.id,
                mcp_product_id="p-1",
                product_name="Товар",
                image_url=None,
                unit_price_retail=100,
                unit_price_wholesale=50,
                wholesale_pack_size=2,
                savings_per_unit=50,
                weighted=False,
                status=DealStatus.collecting,
            )
            session.add(deal)
            await session.flush()
            await session.commit()

            # 1) Додаємо чернетку +1 (ще НЕ в замовленні)
            user_pending, collected, removed = await update_draft(
                session, deal, 1000, "Arthur", 1.0
            )
            assert user_pending == 1.0
            assert collected == 0.0
            assert removed is False
            assert await deal_total(session, deal.id) == 0.0

            # 2) Підтверджуємо — тепер у замовленні
            qty, collected = await confirm_draft(session, deal, 1000)
            assert qty == 1.0
            assert collected == 1.0
            assert await deal_total(session, deal.id) == 1.0
            assert await deal_pending(session, deal.id) == []

            # 3) Підтверджувати вдруге нічого (чернетки нема)
            assert await confirm_draft(session, deal, 1000) is None

            # 4) Після підтвердження ➕ змінює кількість напряму
            user_pending, collected, removed = await update_draft(
                session, deal, 1000, "Arthur", 1.0
            )
            assert user_pending == 2.0
            assert collected == 2.0
            assert deal.status == DealStatus.goal_reached

            # 5) ➖ до нуля — учасник зникає
            await update_draft(session, deal, 1000, "Arthur", -2.0)
            parts = (
                await session.execute(
                    select(Participant).where(Participant.deal_id == deal.id)
                )
            ).scalars().all()
            assert parts == []

        await engine.dispose()

    _run(scenario())
