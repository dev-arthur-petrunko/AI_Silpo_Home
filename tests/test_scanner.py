from core.mcp_client import Product
from core.promo_scanner import filter_new_deals, parse_scan_times


def _product(mcp_id: str, retail: float, wholesale: float, pack: int, in_stock: bool = True) -> Product:
    return Product(
        mcp_id=mcp_id,
        slug=mcp_id,
        name=f"Товар {mcp_id}",
        image_url=None,
        unit_price_retail=retail,
        unit_price_wholesale=wholesale,
        wholesale_pack_size=pack,
        savings_per_unit=round(retail - wholesale, 2),
        discount_percent=round((retail - wholesale) / retail * 100, 2),
        in_stock=in_stock,
        weighted=False,
    )


def test_filter_keeps_above_threshold():
    products = [_product("a", 100, 70, 5)]  # 30% discount
    result = filter_new_deals(products, set(), min_discount_percent=15)
    assert len(result) == 1


def test_filter_drops_below_threshold():
    products = [_product("a", 100, 90, 5)]  # 10% discount
    result = filter_new_deals(products, set(), min_discount_percent=15)
    assert result == []


def test_filter_drops_out_of_stock():
    products = [_product("a", 100, 70, 5, in_stock=False)]
    result = filter_new_deals(products, set(), min_discount_percent=15)
    assert result == []


def test_filter_skips_existing_ids():
    products = [_product("a", 100, 70, 5), _product("b", 100, 60, 10)]
    result = filter_new_deals(products, {"a"}, min_discount_percent=15)
    assert [p.mcp_id for p in result] == ["b"]


def test_filter_sorts_by_discount_desc():
    products = [
        _product("low", 100, 75, 5),  # 25%
        _product("high", 100, 30, 5),  # 70%
        _product("mid", 100, 55, 5),  # 45%
    ]
    result = filter_new_deals(products, set(), min_discount_percent=15)
    assert [p.mcp_id for p in result] == ["high", "mid", "low"]


def test_filter_caps_at_limit():
    products = [
        _product("a", 100, 40, 5),  # 60%
        _product("b", 100, 35, 5),  # 65%
        _product("c", 100, 30, 5),  # 70%
    ]
    result = filter_new_deals(products, set(), min_discount_percent=15, limit=2)
    assert [p.mcp_id for p in result] == ["c", "b"]


def test_parse_scan_times():
    assert parse_scan_times("10:00,14:00,16:00") == [(10, 0), (14, 0), (16, 0)]
    assert parse_scan_times(" 08:30 , 8:30 ") == [(8, 30)]
    assert parse_scan_times("25:00,bad,18:45") == [(18, 45)]
    assert parse_scan_times("") == []


def test_product_from_mcp_quantity_logic():
    raw = {
        "id": "p1",
        "slug": "snek-oreo",
        "name": "Снек Oreo",
        "image": "https://images.silpo.ua/x.png",
        "price": 37.99,
        "oldPrice": None,
        "stock": 57,
        "available": True,
        "weighted": False,
        "specialPrices": [{"price": 18.99, "count": 3, "type": "from"}],
    }
    product = Product.from_mcp(raw)
    assert product is not None
    assert product.wholesale_pack_size == 3
    assert product.unit_price_wholesale == 18.99
    assert product.unit_price_retail == 37.99
    assert product.in_stock is True
    assert product.savings_per_unit == 19.0


def test_product_from_mcp_returns_none_without_special_price():
    raw = {
        "id": "p2",
        "slug": "x",
        "name": "X",
        "price": 10.0,
        "stock": 5,
        "available": True,
        "weighted": False,
        "specialPrices": None,
    }
    assert Product.from_mcp(raw) is None


def test_product_from_mcp_weighted_keeps_fractional_pack():
    raw = {
        "id": "cheese-1",
        "slug": "syr-gauda-amplua",
        "name": "Сир Гауда Амплуа",
        "image": None,
        "price": 949,
        "oldPrice": None,
        "stock": 8,
        "available": True,
        "weighted": True,
        "specialPrices": [{"price": 65.9, "count": 0.5, "type": "from"}],
    }
    product = Product.from_mcp(raw)
    assert product is not None
    assert product.weighted is True
    assert product.wholesale_pack_size == 0.5
    assert product.unit_price_retail == 949.0
    assert product.unit_price_wholesale == 659.0
    assert product.discount_percent == round((949 - 659) / 949 * 100, 2)
