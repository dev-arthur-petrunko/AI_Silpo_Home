# AI Silpo Home

Telegram-бот спільних закупівель для мешканців будинку. Сканує оптові акції «Сільпо»
(промо `melkoopt` / «Гуртом дешевше»), постить їх у груповий чат із фото, збирає
кількість від сусідів, а після збору партії формує зведене замовлення для менеджера.

Статус: **Фаза 0–1** (розвідка MCP + каркас). FSM-хендлери, сканер і менеджерський
флоу — наступні ітерації.

## Стек

- Python 3.14, aiogram 3.x, APScheduler, SQLAlchemy 2 (async) + Alembic
- БД: PostgreSQL (Neon) у продакшні, SQLite локально
- MCP-клієнт: `https://mcp.silpo.ua/mcp` (Bearer-токен), raw JSON-RPC поверх httpx

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # заповнити токени
alembic upgrade head     # міграція (DATABASE_URL у .env)
python main.py
```

Локальна розробка на SQLite: `DATABASE_URL=sqlite+aiosqlite:///./dev.db`.

## MCP «Сільпо» — висновки розвідки (деталі: docs/mcp-notes.md)

- **0.1** — окремої категорії «Сільпо Хоум» немає, але є промо `melkoopt`
  («Гуртом дешевше», 387 товарів). Оптова ціна й розмір партії беруться з поля
  `specialPrices: [{price, count, type:"from"}]` товару.
- **0.2** — image URL є: `image` у списках, `images[]` у деталях. Шлях `send_photo` життєздатний.
- **0.3** — аутентифікація: Bearer access token (OAuth2) у `MCP_API_KEY`.
- Протокол: streamable HTTP, відповіді `tools/call` загортаються в `content[0].text` (JSON-рядок).

## Структура

```
bot/handlers/    FSM: join_deal, confirm_order, manager (наступні фази)
core/config.py   pydantic-settings
core/promo_scanner.py   APScheduler job (заглушка, Фаза 3)
db/models.py     Group, Deal, Participant
db/migrations/   Alembic (initial schema)
scripts/         probe_mcp.py, show_tool_schemas.py, smoke_test.py
docs/mcp-notes.md, docs/raw/
```
