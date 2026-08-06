from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpecialPrice:
    price: float
    count: float
    type: str


def calc_savings(retail: float, wholesale: float) -> float:
    """Savings per unit in currency units."""
    return round(float(retail) - float(wholesale), 2)


def calc_discount_percent(retail: float, wholesale: float) -> float:
    """Discount percentage vs retail price (0..100)."""
    if not retail:
        return 0.0
    return round((float(retail) - float(wholesale)) / float(retail) * 100, 2)


def best_special_price(special_prices: list[dict[str, Any]] | None, retail: float | None) -> SpecialPrice | None:
    """Pick the wholesale tier that gives the lowest unit price.

    `special_prices` entries look like: {"price": 18.99, "count": 3, "type": "from"}.
    Only tiers of type "from" ("від X штук — така ціна") are considered — that is
    the native wholesale structure used for the savings calculation. For weighted
    products `count` is a fractional minimum weight in kg (e.g. 0.5). Tiers with
    price >= retail (no real discount) are ignored. Among equal prices the
    smallest count wins (easier for a group to reach).
    """
    if not special_prices or retail is None:
        return None
    candidates: list[tuple[float, float, str]] = []
    for sp in special_prices:
        price = sp.get("price")
        count = sp.get("count")
        if not isinstance(price, (int, float)) or not isinstance(count, (int, float)):
            continue
        if str(sp.get("type", "")).lower() != "from":
            continue
        if count <= 0 or price >= retail:
            continue
        candidates.append((float(price), float(count), str(sp.get("type", "from"))))
    if not candidates:
        return None
    price, count, kind = min(candidates, key=lambda c: (c[0], c[1]))
    return SpecialPrice(price=price, count=count, type=kind)
