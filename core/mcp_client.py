from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import Settings
from core.savings import best_special_price, calc_discount_percent, calc_savings

logger = logging.getLogger(__name__)

RETRYABLE = (
    httpx.HTTPStatusError,
    httpx.TransportError,
    httpx.TimeoutException,
    TimeoutError,
)


class MCPToolError(Exception):
    """Tool call failed or returned an error payload."""


@dataclass(frozen=True)
class DeliveryContext:
    branch_id: str
    delivery_type: str
    timeslot_start: str
    timeslot_end: str


class Product(BaseModel):
    mcp_id: str
    slug: str
    name: str
    image_url: str | None
    unit_price_retail: float
    unit_price_wholesale: float
    wholesale_pack_size: float
    savings_per_unit: float
    discount_percent: float
    in_stock: bool
    weighted: bool

    @classmethod
    def from_mcp(cls, data: dict[str, Any]) -> "Product | None":
        """Build a Product from a `silpo_get_products` item, resolving the
        quantity-tier price (`specialPrices`). Returns None if the item has no
        wholesale tier or is not available.

        Unit quirk: for weighted products the retail `price` is per kg while the
        wholesale `specialPrices.price` is per 100 g (Silpo sells weighted items
        per 100 g). Without normalizing, every weighted product shows a fake
        ~93% discount, so the wholesale tier is multiplied by 10 (→ per kg)."""
        retail = data.get("price")
        special = best_special_price(data.get("specialPrices"), retail)
        if special is None:
            return None
        stock = data.get("stock") or 0
        weighted = bool(data.get("weighted"))
        wholesale = special.price * 10 if weighted else special.price
        return cls(
            mcp_id=str(data["id"]),
            slug=str(data["slug"]),
            name=str(data["name"]),
            image_url=data.get("image"),
            unit_price_retail=round(float(retail), 2),
            unit_price_wholesale=round(wholesale, 2),
            wholesale_pack_size=special.count,
            savings_per_unit=calc_savings(retail, wholesale),
            discount_percent=calc_discount_percent(retail, wholesale),
            in_stock=bool(data.get("available")) and stock > 0,
            weighted=weighted,
        )


class SilpoMCPClient:
    """Thin wrapper over the Silpo MCP server (streamable HTTP, JSON-RPC 2.0).

    Tool responses are unwrapped from `result.content[0].text` (JSON string).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._session_id: str | None = None
        self._request_id = 0
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if settings.mcp_api_key:
            self._headers["Authorization"] = f"Bearer {settings.mcp_api_key}"
        self._client = httpx.AsyncClient(
            timeout=settings.mcp_request_timeout_seconds,
            headers=self._headers,
        )

    async def __aenter__(self) -> "SilpoMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def connect(self) -> None:
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": self.settings.mcp_protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "ai-silpo-home", "version": "0.1.0"},
            },
        )
        if "result" not in result:
            raise MCPToolError(f"initialize failed: {result!r}")
        logger.info("MCP connected: %s", result.get("result", {}).get("serverInfo"))
        await self._rpc("notifications/initialized", {})

    @retry(
        retry=retry_if_exception_type(RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params:
            payload["params"] = params
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            resp = await self._client.post(
                self.settings.mcp_server_url, json=payload, headers=headers
            )
        except RETRYABLE:
            logger.warning("MCP request failed (retrying): %s %s", method, params)
            raise
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
        if sid:
            self._session_id = sid
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{resp.status_code} {resp.text[:300]}", request=resp.request, response=resp
            )
        return self._parse_body(resp)

    @staticmethod
    def _parse_body(resp: httpx.Response) -> dict[str, Any]:
        if "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        chunks: list[str] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunks.append(line[len("data:"):].strip())
        import json

        return json.loads("".join(chunks))

    @retry(
        retry=retry_if_exception_type((MCPToolError, *RETRYABLE)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        result = response.get("result", {})
        if result.get("isError"):
            text = result.get("content", [{}])[0].get("text", "")
            raise MCPToolError(f"tool {name} error: {text[:300]}")
        content = result.get("content", [])
        if not content:
            return {}
        text = content[0].get("text", "")
        import json

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("tool %s returned non-JSON text", name)
            return {"_text": text}

    async def resolve_delivery_context(self, address: str) -> DeliveryContext:
        addr = await self.call_tool("silpo_find_address", {"address": address})
        addresses = addr.get("addresses", [])
        if not addresses:
            raise MCPToolError(f"address not found: {address}")
        lat, lng = addresses[0]["latitude"], addresses[0]["longitude"]

        delivery = await self.call_tool(
            "silpo_get_available_delivery_types", {"latitude": lat, "longitude": lng}
        )
        branch = self._pick_delivery_option(delivery.get("options", []))
        if branch is None:
            raise MCPToolError("no delivery option with branchId")

        slots = await self.call_tool(
            "silpo_get_time_slots",
            {
                "branchId": branch["branchId"],
                "deliveryTypes": [branch["deliveryType"]],
                "limit": 30,
                "start": self._tomorrow_iso(),
            },
        )
        available = [s for s in slots.get("slots", []) if s.get("available")]
        if not available:
            raise MCPToolError("no available time slots for delivery type")
        slot = available[0]
        return DeliveryContext(
            branch_id=branch["branchId"],
            delivery_type=branch["deliveryType"],
            timeslot_start=slot["start"],
            timeslot_end=slot["end"],
        )

    def _pick_delivery_option(self, options: list[dict[str, Any]]) -> dict[str, Any] | None:
        pref = self.settings.delivery_type_preference
        if pref:
            for opt in options:
                if opt.get("deliveryType") == pref and opt.get("branchId"):
                    return opt
        for preferred in ("WideAssortDelivery", "DeliveryHome"):
            for opt in options:
                if opt.get("deliveryType") == preferred and opt.get("branchId"):
                    return opt
        for opt in options:
            if opt.get("branchId"):
                return opt
        return None

    @staticmethod
    def _tomorrow_iso() -> str:
        import datetime as dt

        tomorrow = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
        return tomorrow.replace(minute=0, second=0, microsecond=0).isoformat()

    async def get_wholesale_products(
        self, ctx: DeliveryContext, promotion_code: str = "melkoopt", max_pages: int = 15
    ) -> list[Product]:
        """Fetch products of the wholesale promotion and resolve quantity tiers.

        Pages are fetched concurrently (after reading meta.total from page 0)
        so the scan stays fast even when the promotion has many products."""
        import asyncio

        base = {
            "branchId": ctx.branch_id,
            "deliveryType": ctx.delivery_type,
            "timeslotStart": ctx.timeslot_start,
            "timeslotEnd": ctx.timeslot_end,
            "promotionCode": promotion_code,
            "limit": 100,
        }
        first = await self.call_tool("silpo_get_products", {**base, "offset": 0})
        total = first.get("meta", {}).get("total")

        offsets: list[int] = []
        if total is not None:
            for offset in range(base["limit"], min(total, max_pages * base["limit"]), base["limit"]):
                offsets.append(offset)
        else:
            offsets = [page * base["limit"] for page in range(1, max_pages)]

        pages: list[dict[str, Any]] = [first]
        if offsets:
            results = await asyncio.gather(
                *(self.call_tool("silpo_get_products", {**base, "offset": offset}) for offset in offsets),
                return_exceptions=True,
            )
            for offset, result in zip(offsets, results):
                if isinstance(result, Exception):
                    logger.warning("page offset=%s failed: %r", offset, result)
                    continue
                pages.append(result)

        products: list[Product] = []
        seen: set[str] = set()
        for data in pages:
            for item in data.get("products", []):
                product = Product.from_mcp(item)
                if product is None or product.mcp_id in seen:
                    continue
                seen.add(product.mcp_id)
                products.append(product)
        logger.info("fetched %d wholesale products (promotion=%s)", len(products), promotion_code)
        return products

    async def get_product_details(self, ctx: DeliveryContext, slug: str) -> dict[str, Any]:
        return await self.call_tool(
            "silpo_get_product_details",
            {
                "branchId": ctx.branch_id,
                "slug": slug,
                "deliveryType": ctx.delivery_type,
                "timeslotStart": ctx.timeslot_start,
                "timeslotEnd": ctx.timeslot_end,
            },
        )
