import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


async def main():
    from core.config import get_settings
    from core.mcp_client import SilpoMCPClient

    s = get_settings()
    async with SilpoMCPClient(s) as c:
        ctx = await c.resolve_delivery_context(s.delivery_address)
        promos = await c.call_tool(
            "silpo_get_promotions",
            {
                "branchId": ctx.branch_id,
                "deliveryType": ctx.delivery_type,
                "timeslotStart": ctx.timeslot_start,
                "timeslotEnd": ctx.timeslot_end,
            },
        )
        print("summary:", promos.get("summary"))
        for pr in promos.get("promotions", []):
            print(f"  - {pr['code']}: {pr['title']} ({pr.get('productCount')} товарів)")
        mel = next((p for p in promos.get("promotions", []) if p["code"] == "melkoopt"), None)
        print("\nmelkoopt active:", bool(mel))


asyncio.run(main())
