"""Phase 1 smoke test: config, models, DB CRUD round-trip, scheduler wiring.

Usage:
    python scripts/smoke_test.py
Uses a temporary SQLite DB (does not touch real DB or Telegram).
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./dev_smoke.db"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
os.environ.pop("MCP_API_KEY", None)

from sqlalchemy import select  # noqa: E402

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from aiogram import Bot  # noqa: E402

from core.config import get_settings  # noqa: E402
from core.promo_scanner import schedule_jobs  # noqa: E402
from db.base import Base  # noqa: E402
from db.models import Deal, DealStatus, Group, Participant  # noqa: E402
from db.session import get_sessionmaker, init_engine  # noqa: E402

SMOKE_DB = ROOT / "dev_smoke.db"
CHAT_ID = -100123456789


async def main() -> None:
    SMOKE_DB.unlink(missing_ok=True)
    settings = get_settings()
    assert settings.telegram_bot_token, "config token"
    assert settings.min_discount_percent == 15.0, "config discount"
    print("[ok] config loaded:", settings.database_url)

    engine = init_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[ok] tables created")

    sm = get_sessionmaker()

    # Session 1: happy-path insert
    async with sm() as session:
        group = Group(telegram_chat_id=CHAT_ID, house_name="Шевченка 12")
        session.add(group)
        await session.commit()
        deal = Deal(
            group_id=group.id,
            mcp_product_id="1ed09877-test",
            product_name="Снек Oreo молочний",
            image_url="https://images.silpo.ua/x.png",
            unit_price_retail=37.99,
            unit_price_wholesale=18.99,
            wholesale_pack_size=3,
            savings_per_unit=19.00,
            status=DealStatus.collecting,
        )
        session.add(deal)
        await session.commit()
        session.add_all(
            [
                Participant(deal_id=deal.id, telegram_user_id=111, telegram_username="@ivan", quantity=2),
                Participant(deal_id=deal.id, telegram_user_id=222, telegram_username=None, quantity=1),
            ]
        )
        await session.commit()
        print("[ok] group + deal + 2 participants persisted")

    # Session 2: duplicate (deal_id, telegram_user_id) must be rejected
    async with sm() as session:
        deal_id = (
            await session.execute(select(Deal.id).where(Deal.mcp_product_id == "1ed09877-test"))
        ).scalar_one()
        session.add(Participant(deal_id=deal_id, telegram_user_id=111, quantity=5))
        try:
            await session.commit()
            raise AssertionError("unique(deal_id, user_id) not enforced")
        except Exception:
            await session.rollback()
        print("[ok] unique(deal_id, telegram_user_id) enforced")

    # Session 3: verify data from fresh session
    async with sm() as session:
        group_db = (
            await session.execute(select(Group).where(Group.telegram_chat_id == CHAT_ID))
        ).scalar_one()
        deals = (await session.execute(select(Deal).where(Deal.group_id == group_db.id))).scalars().all()
        assert len(deals) == 1
        assert deals[0].product_name == "Снек Oreo молочний"
        parts = (await session.execute(select(Participant).where(Participant.deal_id == deals[0].id))).scalars().all()
        assert len(parts) == 2, f"expected 2, got {len(parts)}"
        assert sorted(p.telegram_user_id for p in parts) == [111, 222]
        print(f"[ok] verified: deal {deals[0].id}, participants={len(parts)}, pack_size={deals[0].wholesale_pack_size}")

    # scheduler wiring
    bot = Bot(token=settings.telegram_bot_token)
    scheduler = AsyncIOScheduler(timezone="UTC")
    schedule_jobs(scheduler, bot, settings)
    jobs = scheduler.get_jobs()
    assert any(j.id == "scan_promotions" for j in jobs), "scan_promotions job missing"
    print("[ok] scheduler has jobs:", [j.id for j in jobs])

    if scheduler.running:
        scheduler.shutdown(wait=False)
    await bot.session.close()
    await engine.dispose()

    SMOKE_DB.unlink(missing_ok=True)
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
