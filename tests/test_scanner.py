from core.config import Settings
from core.mcp_client import Product
from core.promo_scanner import filter_new_deals, group_delivery_address, parse_scan_times
from db.models import Group

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


def test_group_delivery_address_falls_back_to_settings():
    settings = Settings(telegram_bot_token="x")
    group = Group(telegram_chat_id=1)
    assert group_delivery_address(group, settings) == settings.delivery_address


def test_group_delivery_address_uses_group_city():
    settings = Settings(telegram_bot_token="x")
    group = Group(telegram_chat_id=1, delivery_address="Львів")
    assert group_delivery_address(group, settings) == "Львів"
    group.delivery_address = "   "
    assert group_delivery_address(group, settings) == settings.delivery_address


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


def test_scan_skips_failed_city_but_posts_others():
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import core.promo_scanner as ps
    from core.promo_scanner import scan_promotions
    from db.base import Base
    from db.models import Group as GroupModel

    class FakeMessage:
        def __init__(self, message_id: int) -> None:
            self.message_id = message_id

    class FakeBot:
        async def send_photo(self, chat_id, photo, caption=None, reply_markup=None):
            return FakeMessage(1000 + chat_id)

        async def send_message(self, chat_id, text, reply_markup=None, link_preview_options=None):
            return FakeMessage(2000 + chat_id)

    class FakeMCP:
        def __init__(self, settings) -> None:
            self.settings = settings

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def resolve_delivery_context(self, address):
            if address == "Погане місто":
                raise RuntimeError("no available time slots")
            return "ctx-" + address

        async def get_wholesale_products(self, ctx):
            return [_product("c1", 100, 40, 5)]  # 60% discount

    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session:
            session.add(GroupModel(telegram_chat_id=-111, house_name="А", delivery_address="Погане місто"))
            session.add(GroupModel(telegram_chat_id=-222, house_name="Б", delivery_address="Харків"))
            await session.commit()

        settings = Settings(telegram_bot_token="x")
        original = ps.SilpoMCPClient
        ps.SilpoMCPClient = FakeMCP
        try:
            async with factory() as session:
                stats = await scan_promotions(FakeBot(), settings, session=session)
        finally:
            ps.SilpoMCPClient = original
        await engine.dispose()
        return stats

    loop = asyncio.new_event_loop()
    try:
        stats = loop.run_until_complete(scenario())
    finally:
        loop.close()

    assert len(stats["posted"]) == 1
    assert stats["posted"][0].startswith("-222:")
