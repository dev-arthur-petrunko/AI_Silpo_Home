from core.savings import best_special_price, calc_discount_percent, calc_savings


def test_calc_savings():
    assert calc_savings(37.99, 18.99) == 19.0
    assert calc_savings(10, 8) == 2.0


def test_calc_discount_percent():
    assert calc_discount_percent(100, 75) == 25.0
    assert calc_discount_percent(0, 0) == 0.0
    assert calc_discount_percent(37.99, 18.99) == round((37.99 - 18.99) / 37.99 * 100, 2)


def test_best_special_price_ignores_no_discount():
    assert best_special_price([{"price": 99, "count": 3, "type": "from"}], 50) is None
    assert best_special_price(None, 50) is None
    assert best_special_price([], 50) is None


def test_best_special_price_picks_lowest_price():
    special = best_special_price(
        [
            {"price": 40, "count": 2, "type": "from"},
            {"price": 30, "count": 10, "type": "from"},
        ],
        retail=50,
    )
    assert special is not None
    assert special.price == 30
    assert special.count == 10


def test_best_special_price_tie_breaks_smaller_count():
    special = best_special_price(
        [
            {"price": 30, "count": 5, "type": "from"},
            {"price": 30, "count": 3, "type": "from"},
        ],
        retail=50,
    )
    assert special is not None
    assert special.count == 3


def test_best_special_price_skips_bad_entries():
    special = best_special_price(
        [
            {"price": None, "count": 3},
            {"price": 20, "count": 0},
            {"price": 25, "count": 4, "type": "from"},
        ],
        retail=50,
    )
    assert special is not None
    assert special.price == 25
    assert special.count == 4


def test_best_special_price_keeps_fractional_weighted_count():
    special = best_special_price(
        [{"price": 65.9, "count": 0.5, "type": "from"}],
        retail=949,
    )
    assert special is not None
    assert special.price == 65.9
    assert special.count == 0.5


def test_best_special_price_picks_lowest_weighted_price():
    special = best_special_price(
        [
            {"price": 49.9, "count": 0.3, "type": "from"},
            {"price": 44.9, "count": 0.4, "type": "from"},
        ],
        retail=689,
    )
    assert special is not None
    assert special.price == 44.9
    assert special.count == 0.4
