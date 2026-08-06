from core.config import Settings
from core.llm import extract_json
from core.reminders import build_reminder_text, frequency_label
from core.tone_profiler import tone_intro, tone_outro


def _settings(groq_key: str | None) -> Settings:
    return Settings(
        telegram_bot_token="test",
        groq_api_key=groq_key,
        database_url="sqlite+aiosqlite:///:memory:",
        _env_file=None,
    )


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_code_fence():
    text = '```json\n{"tone": "дружній", "emoji": true}\n```'
    assert extract_json(text) == {"tone": "дружній", "emoji": True}


def test_extract_json_wrapped_in_prose():
    text = 'Ось профіль: {"post_intro": "Сусіди, дивіться!"} Готово.'
    assert extract_json(text) == {"post_intro": "Сусіди, дивіться!"}


def test_tone_intro_outro():
    assert tone_intro(None) is None
    assert tone_outro(None) is None
    profile = {"post_intro": "Сусіди, дивіться! 🔥", "post_outro": "Встигни замовити!"}
    assert tone_intro(profile) == "Сусіди, дивіться! 🔥"
    assert tone_outro(profile) == "Встигни замовити!"
    assert tone_intro({"post_intro": "  "}) is None
    assert tone_outro({"post_outro": ""}) is None


def test_frequency_label():
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monthly = [base, base + timedelta(days=28), base + timedelta(days=57)]
    assert frequency_label(monthly) == "раз на місяць"

    weekly = [base, base + timedelta(days=7), base + timedelta(days=14)]
    assert frequency_label(weekly) == "раз на один-два тижні"

    assert frequency_label([]) is None
    assert frequency_label([base]) is None


def test_build_reminder_text_template_fallback():
    text = build_reminder_text_sync()

    # без ключа Groq -> шаблонний fallback з назвою товару
    assert "Масло вершкове" in text


def build_reminder_text_sync() -> str:
    import asyncio

    return asyncio.run(
        build_reminder_text(
            _settings(groq_key=None),
            product_name="Масло вершкове",
            category="масло",
            frequency="раз на місяць",
        )
    )


def test_format_deal_record_uses_tone():
    from bot.texts import format_deal_record

    class FakeDeal:
        product_name = "Сир Буррата"
        image_url = None
        unit_price_retail = 949
        unit_price_wholesale = 65.9
        wholesale_pack_size = 0.5
        savings_per_unit = 883.1
        weighted = True
        deadline_at = None

    profile = {"post_intro": "Сусіди, топ-знижка! 🔥", "post_outro": "Встигни замовити!"}
    text = format_deal_record(FakeDeal(), collected=0.5, tone_profile=profile)
    assert text.startswith("Сусіди, топ-знижка! 🔥")
    assert "Встигни замовити!" in text

    neutral = format_deal_record(FakeDeal(), collected=0.5, tone_profile=None)
    assert not neutral.startswith("Сусіди")
    assert "Встигни замовити!" not in neutral
