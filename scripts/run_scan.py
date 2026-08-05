"""Run one scan of wholesale deals.

Usage:
    python scripts/run_scan.py --dry-run      # fetch + print deals (no DB, no Telegram)
    python scripts/run_scan.py --post         # real run: post to active groups (bot + DB)

Examples:
    python scripts/run_scan.py --dry-run --min 25 --limit 20
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def _fmt(value: float | int) -> str:
    return f"{int(value)}" if float(value) == int(value) else f"{value:.2f}"


def _fmt_qty(value: float | int) -> str:
    return f"{int(value)}" if float(value) == int(value) else f"{value:g}"


async def dry_run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from core.mcp_client import SilpoMCPClient

    settings = get_settings()
    async with SilpoMCPClient(settings) as mcp:
        ctx = await mcp.resolve_delivery_context(settings.delivery_address)
        print(f"Context: branch={ctx.branch_id} type={ctx.delivery_type}")
        products = await mcp.get_wholesale_products(ctx)

    threshold = args.min if args.min is not None else settings.min_discount_percent
    hits = [p for p in products if p.discount_percent >= threshold and p.in_stock]
    hits.sort(key=lambda p: p.discount_percent, reverse=True)

    print(f"\n{'#':>3} {'Знижка':>7} {'Роздріб':>8} {'Опт':>8} {'Партія':>7}  {'Товар'}")
    for i, p in enumerate(hits[: args.limit], 1):
        unit = "кг" if p.weighted else "шт"
        print(
            f"{i:>3} {_fmt(p.discount_percent):>6}% {_fmt(p.unit_price_retail):>8} "
            f"{_fmt(p.unit_price_wholesale):>8} {_fmt_qty(p.wholesale_pack_size):>6} {unit}  {p.name}"
        )
    print(f"\nВсього: {len(hits)} угод зі знижкою >= {_fmt(threshold)}% (з {len(products)} знайдених)")
    return 0


async def post_run(_args: argparse.Namespace) -> int:
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    from core.config import get_settings
    from core.promo_scanner import scan_promotions
    from db.session import dispose_engine, init_engine

    settings = get_settings()
    init_engine(settings.database_url)
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        stats = await scan_promotions(bot, settings)
        print("posted:", len(stats["posted"]))
        for item in stats["posted"]:
            print("  ", item)
        print("skipped_dup:", stats["skipped_dup"], "| below_threshold:", stats["below_threshold"])
    finally:
        await bot.session.close()
        await dispose_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Silpo wholesale scanner run")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="fetch and print (default)")
    group.add_argument("--post", action="store_true", help="post deals to active groups")
    parser.add_argument("--min", type=float, default=None, help="override MIN_DISCOUNT_PERCENT")
    parser.add_argument("--limit", type=int, default=40, help="print limit (dry-run)")
    args = parser.parse_args()

    if args.post:
        return asyncio.run(post_run(args))
    return asyncio.run(dry_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
