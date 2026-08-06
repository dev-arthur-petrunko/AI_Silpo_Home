import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Deal, DealStatus, Group, Participant
from main import RESET_STATUSES, reset_house_order


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _make_group(session):
    group = Group(telegram_chat_id=-100, house_name="Тест")
    session.add(group)
    await session.flush()
    return group


async def _make_deal(session, group, status, participants=1, counter=None):
    deal = Deal(
        group_id=group.id,
        mcp_product_id=f"p-{status.value}-{counter or 0}",
        product_name=f"Товар {status.value}",
        image_url=None,
        unit_price_retail=100,
        unit_price_wholesale=50,
        wholesale_pack_size=2,
        savings_per_unit=50,
        weighted=False,
        status=status,
        telegram_message_id=12345,
    )
    session.add(deal)
    await session.flush()
    for i in range(participants):
        session.add(
            Participant(
                deal_id=deal.id,
                telegram_user_id=1000 + i,
                telegram_username=f"u{i}",
                quantity=1,
            )
        )
    return deal


def test_reset_statuses_include_confirmed():
    assert DealStatus.confirmed in RESET_STATUSES


def test_reset_house_order_clears_everything():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session:
            group = await _make_group(session)
            collecting = await _make_deal(session, group, DealStatus.collecting, counter=0)
            goal = await _make_deal(session, group, DealStatus.goal_reached, counter=1)
            confirmed = await _make_deal(session, group, DealStatus.confirmed, counter=2)
            sent = await _make_deal(session, group, DealStatus.sent_to_manager, counter=3)
            expired = await _make_deal(session, group, DealStatus.expired, participants=0, counter=4)
            group.delivery_info = {
                "city": "Харьков",
                "address": "вул. 1",
                "delivery_time": "18 до 20:00",
                "phone": "0953333902",
            }
            group.checkout_pending = True
            await session.commit()

            affected = await reset_house_order(session, group)

            statuses = {
                deal.id: deal.status
                for deal in (
                    await session.execute(select(Deal).where(Deal.group_id == group.id))
                ).scalars()
            }
            counts = (
                await session.execute(
                    select(Participant).where(
                        Participant.deal_id.in_(
                            [collecting.id, goal.id, confirmed.id, sent.id]
                        )
                    )
                )
            ).scalars().all()

            assert statuses[collecting.id] == DealStatus.collecting
            assert statuses[goal.id] == DealStatus.collecting
            assert statuses[confirmed.id] == DealStatus.collecting
            assert statuses[sent.id] == DealStatus.collecting
            assert statuses[expired.id] == DealStatus.expired
            assert counts == []
            assert group.delivery_info is None
            assert group.checkout_pending is False
            assert set(affected) == {collecting, goal, confirmed, sent}

        await engine.dispose()

    _run(scenario())
