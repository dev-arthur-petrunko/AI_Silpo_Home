"""One-off probe of the Silpo MCP server (Phase 0 reconnaissance).

Usage:
    python scripts/probe_mcp.py
Reads MCP_SERVER_URL and MCP_API_KEY from .env (via pydantic-settings default config
or environment). Prints raw JSON-RPC responses to stdout and appends them to
docs/mcp-notes.md.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Minimal local env loader (avoid importing core.config yet — phase 0 has no deps
# beyond httpx; but if pydantic-settings is available, reuse core.config).
try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False


load_dotenv(ROOT / ".env")

SERVER_URL = os.getenv("MCP_SERVER_URL", "https://mcp.silpo.ua/mcp")
ACCESS_TOKEN = os.getenv("MCP_API_KEY", "")

NOTES_PATH = ROOT / "docs" / "mcp-notes.md"  # static summary; raw logs go to docs/raw/

MCP_PROTOCOL_VERSION = "2025-06-18"


class McpProbe:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.session_id: str | None = None
        self._request_id = 0

    def _headers(self) -> dict:
        h = dict(self.headers)
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    async def _rpc(self, method: str, params: dict | None = None) -> httpx.Response:
        self._request_id += 1
        body = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params is not None:
            body["params"] = params
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self.url, headers=self._headers(), json=body)
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        return resp

    async def initialize(self) -> dict:
        resp = await self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ai-silpo-home-probe", "version": "0.0.1"},
            },
        )
        return self._parse(resp)

    async def initialized_notification(self) -> None:
        await self._rpc("notifications/initialized")

    async def list_tools(self) -> dict:
        resp = await self._rpc("tools/list")
        return self._parse(resp)

    async def call_tool(self, name: str, arguments: dict) -> dict:
        resp = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        return self._parse(resp)

    async def call_tool_json(self, name: str, arguments: dict) -> dict:
        """Call a tool and return the JSON parsed from content[0].text."""
        raw = await self.call_tool(name, arguments)
        content = raw.get("result", {}).get("content", [])
        if not content:
            return {"_raw": raw}
        text = content[0].get("text", "")
        if "isError" in raw.get("result", {}) and raw["result"].get("isError"):
            return {"_error": text, "_raw": raw}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_text": text, "_raw": raw}

    @staticmethod
    def _parse(resp: httpx.Response) -> dict:
        if resp.status_code >= 400:
            return {
                "http_status": resp.status_code,
                "http_headers": dict(resp.headers),
                "raw": resp.text[:2000],
            }
        if "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        # SSE stream (text/event-stream)
        text = resp.text
        data_chunks = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                data_chunks.append(line[len("data:"):].strip())
        try:
            return json.loads("".join(data_chunks))
        except json.JSONDecodeError:
            return {"raw_sse": text[:2000]}


async def main() -> None:
    probe = McpProbe(SERVER_URL, ACCESS_TOKEN)
    log: list[str] = []

    init = await probe.initialize()
    log.append("### initialize")
    log.append(json.dumps(init, ensure_ascii=False, indent=2)[:4000])
    print(json.dumps(init, ensure_ascii=False, indent=2)[:4000])

    await probe.initialized_notification()

    tools = await probe.list_tools()
    log.append("\n### tools/list")
    log.append(json.dumps(tools, ensure_ascii=False, indent=2))
    names = [t.get("name") for t in tools.get("result", {}).get("tools", [])]
    print("TOOLS:", ", ".join(names))

    if "--chain" in sys.argv:
        log.append("\n### chain: address -> delivery -> slots -> catalog")
        await run_chain(probe, log)

    raw_dir = ROOT / "docs" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    raw_path = raw_dir / f"probe-{stamp}.md"
    raw_path.write_text(
        f"# Raw probe log {stamp}\n\n"
        f"- Server URL: `{SERVER_URL}`\n"
        "- Auth: Bearer access token\n"
        f"- Protocol version: `{MCP_PROTOCOL_VERSION}`\n\n"
        + "\n\n".join(log)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nSaved raw responses to {raw_path}")


async def run_chain(probe: McpProbe, log: list[str]) -> None:
    def dump(tag: str, data: dict, limit: int = 3500) -> None:
        log.append(f"\n#### {tag}")
        log.append(json.dumps(data, ensure_ascii=False, indent=2)[:limit])
        print(f"#### {tag}: {json.dumps(data, ensure_ascii=False)[:300]}")

    addr = await probe.call_tool_json("silpo_find_address", {"address": "Київ, вул. Богдана Хмельницького, 1"})
    dump("find_address", addr, 1500)
    lat = addr["addresses"][0]["latitude"]
    lng = addr["addresses"][0]["longitude"]

    delivery = await probe.call_tool_json("silpo_get_available_delivery_types", {"latitude": lat, "longitude": lng})
    dump("available_delivery_types", delivery, 4000)
    options = delivery["options"]
    branch = next((o for o in options if o.get("branchId")), options[0])
    branch_id = branch.get("branchId")
    delivery_type = branch["deliveryType"]

    import datetime as _dt
    tomorrow = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=1)
    tomorrow_iso = tomorrow.replace(minute=0, second=0, microsecond=0).isoformat()
    slots = await probe.call_tool_json(
        "silpo_get_time_slots",
        {"branchId": branch_id, "deliveryTypes": [delivery_type], "limit": 30, "start": tomorrow_iso},
    )
    dump("time_slots", slots, 2500)
    available = [s for s in slots["slots"] if s.get("available")]
    if not available:
        print("NO AVAILABLE SLOTS; trying without start filter")
        slots = await probe.call_tool_json(
            "silpo_get_time_slots", {"branchId": branch_id, "deliveryTypes": [delivery_type], "limit": 30},
        )
        dump("time_slots_retry", slots, 2500)
        available = [s for s in slots["slots"] if s.get("available")]
    slot = available[0]
    ts_start, ts_end = slot["start"], slot["end"]

    ctx = {"branchId": branch_id, "deliveryType": delivery_type,
           "timeslotStart": ts_start, "timeslotEnd": ts_end}
    log.append(f"\n#### resolved context: {json.dumps(ctx)}")
    print("RESOLVED:", json.dumps(ctx))

    categories = await probe.call_tool_json("silpo_get_categories", {"branchId": branch_id})
    dump("categories_top", categories, 3000)

    tree = await probe.call_tool_json("silpo_get_categories_tree", ctx)
    dump("categories_tree", tree, 200000)

    sets = await probe.call_tool_json("silpo_get_product_sets", {"branchId": branch_id})
    dump("product_sets", sets, 4000)

    promos = await probe.call_tool_json("silpo_get_promotions", ctx)
    dump("promotions", promos, 4000)

    promo_products = await probe.call_tool_json(
        "silpo_get_products",
        {**ctx, "mustHavePromotion": True, "limit": 20},
    )
    dump("products_mustHavePromotion", promo_products, 6000)

    prods = promo_products.get("products", [])
    if prods:
        first = prods[0]
        details = await probe.call_tool_json("silpo_get_product_details", {**ctx, "slug": first["slug"]})
        dump("product_details", details, 6000)

    melkoopt = await probe.call_tool_json(
        "silpo_get_products",
        {**ctx, "promotionCode": "melkoopt", "limit": 15},
    )
    dump("products_melkoopt", melkoopt, 8000)
    mp = melkoopt.get("products", [])
    with_special = [p for p in mp if p.get("specialPrices")]
    log.append(f"\n#### melkoopt: total={len(mp)}, with_specialPrices={len(with_special)}")
    print(f"MELKOOPT: total={len(mp)}, with_specialPrices={len(with_special)}")
    if with_special:
        log.append("```json\n" + json.dumps(with_special[:3], ensure_ascii=False, indent=2) + "\n```")


if __name__ == "__main__":
    asyncio.run(main())

