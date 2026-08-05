from bot.keyboards import deal_keyboard, parse_deal_dec, parse_deal_inc, parse_deal_join, deal_step
from bot.texts import fmt_qty, format_deal_record, format_order_text, pack_unit
from core.orders import next_quantity, should_remove


def _fake_deal(**overrides):
    class FakeDeal:
        pass

    deal = FakeDeal()
    deal.product_name = "Сир Буррата"
    deal.image_url = None
    deal.unit_price_retail = 949
    deal.unit_price_wholesale = 65.9
    deal.wholesale_pack_size = 0.5
    deal.savings_per_unit = 883.1
    deal.weighted = True
    deal.deadline_at = None
    for key, value in overrides.items():
        setattr(deal, key, value)
    return deal


def test_fmt_qty():
    assert fmt_qty(3) == "3"
    assert fmt_qty(0.5) == "0.5"
    assert fmt_qty(1.0) == "1"


def test_pack_unit():
    assert pack_unit(True) == "кг"
    assert pack_unit(False) == "шт"


def test_deal_step():
    assert deal_step(True) == 0.5
    assert deal_step(False) == 1.0


def test_format_deal_record_weighted():
    text = format_deal_record(_fake_deal(), collected=1.0)
    assert "0.5 кг" in text
    assert "65.90₴/кг" in text
    assert "Зібрано: <b>1/0.5 кг</b>" in text


def test_format_deal_record_piece():
    text = format_deal_record(_fake_deal(weighted=False, wholesale_pack_size=3, unit_price_retail=37.99, unit_price_wholesale=18.99, savings_per_unit=19.0), collected=2)
    assert "3 шт" in text
    assert "18.99₴/шт" in text
    assert "Зібрано: <b>2/3 шт</b>" in text


def test_format_order_text():
    text = format_order_text([("Група 1", ["• Товар: 1 шт × 5₴ = 5₴"])], total_cost=5, total_savings=2)
    assert "Разом: <b>5.00₴</b>" in text
    assert "Ти економиш: <b>2.00₴</b>" in text


def test_next_quantity():
    assert next_quantity(0, 0.5) == 0.5
    assert next_quantity(1, -0.5) == 0.5
    assert next_quantity(0.5, -0.5) == 0.0


def test_should_remove():
    assert should_remove(0)
    assert should_remove(-0.5)
    assert not should_remove(0.5)


def test_deal_keyboard_and_parsers():
    kb = deal_keyboard(7, 0.5, True)
    flat = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "deal:inc:7" in flat
    assert "deal:dec:7" in flat
    assert "deal:join:7" in flat
    assert parse_deal_join("deal:join:7") == 7
    assert parse_deal_inc("deal:inc:7") == 7
    assert parse_deal_dec("deal:dec:7") == 7
    assert parse_deal_join("x") is None
    assert parse_deal_inc("deal:join:7") is None
