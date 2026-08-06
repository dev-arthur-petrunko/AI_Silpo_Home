from bot.keyboards import manager_status_keyboard, parse_manager_status
from bot.texts import ORDER_STATUS_LABELS, order_status_text


def test_order_status_text_labels():
    assert order_status_text("pending") == "⏳ Очікує підтвердження менеджера"
    assert order_status_text("confirmed") == "✅ Підтверджено"
    assert order_status_text("packing") == "📦 Комплектується"
    assert order_status_text("delivering") == "🚚 В дорозі"
    assert order_status_text("done") == "🎉 Виконано"
    assert order_status_text("cancelled") == "❌ Скасовано"
    assert order_status_text(None) == "—"
    assert order_status_text("unknown") == "—"


def test_manager_status_keyboard_has_all_statuses():
    kb = manager_status_keyboard(7)
    buttons = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "mgr:status:confirmed:7" in buttons
    assert "mgr:status:cancelled:7" in buttons
    assert "mgr:status:packing:7" in buttons
    assert "mgr:status:delivering:7" in buttons
    assert "mgr:status:done:7" in buttons


def test_parse_manager_status():
    assert parse_manager_status("mgr:status:confirmed:7") == ("confirmed", 7)
    assert parse_manager_status("mgr:status:done:123") == ("done", 123)
    assert parse_manager_status("mgr:status:packing:abc") is None
    assert parse_manager_status("deal:join:5") is None
    assert parse_manager_status("") is None
