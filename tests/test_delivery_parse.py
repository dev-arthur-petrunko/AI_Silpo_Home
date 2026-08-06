from main import _parse_delivery_info


def test_observed_free_text():
    """Той самий ввід, що ламався: без розділювачів міста/адреси,
    «да» замість «до», слово «телефон»."""
    result = _parse_delivery_info(
        "харьков вул нескорених4 40, кв 143 доставка с 18 да 20-00 телефон 0953333903"
    )
    assert result == (
        "харьков",
        "вул нескорених4 40 кв 143",
        "18-20:00",
        "0953333903",
    )


def test_pipe_separated():
    result = _parse_delivery_info(
        "Київ | вул. Хрещатик, 1, кв. 5 | 18:00-21:00 | +380 50 123 45 67"
    )
    assert result == (
        "Київ",
        "вул. Хрещатик 1 кв. 5",
        "18:00-21:00",
        "+380 50 123 45 67",
    )


def test_comma_separated():
    result = _parse_delivery_info(
        "Харьков, вул Нескорених 50, кв 6, 18 до 20:00, 0953333902"
    )
    assert result == (
        "Харьков",
        "вул Нескорених 50 кв 6",
        "18 до 20:00",
        "0953333902",
    )


def test_city_prefix_stripped():
    result = _parse_delivery_info(
        "м. Київ, вул Хрещатик 1, кв 5, 18 до 20:00, 0953333902"
    )
    assert result is not None
    assert result[0] == "Київ"


def test_missing_phone():
    assert _parse_delivery_info("Київ, вул Хрещатик 1, 18:00-21:00") is None


def test_missing_time():
    assert _parse_delivery_info("Київ, вул Хрещатик 1, 0953333902") is None
