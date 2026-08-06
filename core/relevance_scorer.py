"""Пріоритизація акційних товарів (melkoopt) під конкретну групу-будинок.

Ключові ідеї:
1. TF-IDF + косинусна схожість — без важких залежностей (без sklearn/torch).
2. Профіль будинку рахується з ДВОХ сигналів:
   - позитив: товари, які реально замовили (Deal.status == "confirmed")
   - негатив: товари, які постили кілька разів, а ніхто не приєднався
     (Deal.status == "expired" з малою кількістю учасників)
3. Категорії — фіксований список (м'ясо, молочка, масло, каші, риба, солодке),
   визначаються по ключових словах у назві товару.
4. Explore/exploit: щоденна добірка постів НЕ складається тільки з "топ за
   рахунком" — гарантовано резервується місце для категорії, яка давно/погано
   показувала себе, щоб не ховати її назавжди (людям сьогодні не треба,
   завтра може знадобитись).

Чиста частина (категорії, TF-IDF, рейтинг) самодостатня і тестована без БД.
Інтеграція з БД — у кінці файлу: get_group_deal_history / pick_products_for_group.
"""
from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. КАТЕГОРІЇ — фіксований список, ключові слова українською (lowercase)
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "м'ясо": [
        "м'ясо", "мясо", "курка", "курятина", "куряча", "свинина", "яловичина",
        "фарш", "ковбаса", "сосиски", "бекон", "філе", "стегно", "гомілка",
        "індичка", "баранина", "шинка", "сало",
    ],
    "молочка": [
        "молоко", "кефір", "йогурт", "сметана", "ряжанка", "сир",
        "творог", "сирок", "вершки", "простокваша", "айран",
    ],
    "масло": [
        "масло", "олія", "маргарин", "спред",
    ],
    "каші": [
        "крупа", "гречка", "рис", "вівсянка", "пшоно", "перловка",
        "манка", "макарони", "спагеті", "булгур", "кус-кус", "мюслі", "борошно",
    ],
    "риба": [
        "риба", "оселедець", "лосось", "скумбрія", "тунець", "кальмар",
        "креветки", "минтай", "консерва", "ікра",
    ],
    "солодке": [
        "цукерки", "шоколад", "печиво", "торт", "вафлі", "цукерка",
        "мармелад", "зефір", "халва", "джем", "варення", "мед", "печіння",
    ],
}

DEFAULT_CATEGORY = "інше"


def categorize_product(name: str) -> str:
    """Визначає категорію товару по ключових словах у назві.
    Перше співпадіння перемагає (порядок словника вище — пріоритет)."""
    lowered = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                return category
    return DEFAULT_CATEGORY


# ---------------------------------------------------------------------------
# 2. TF-IDF + косинусна схожість (чистий Python, без залежностей)
# ---------------------------------------------------------------------------

def _tokenize(name: str) -> list[str]:
    return [w for w in name.lower().replace(",", " ").split() if len(w) > 1]


def tf_idf_vectors(product_names: list[str]) -> list[dict[str, float]]:
    """Повертає список TF-IDF векторів (словник слово->вага) для кожної назви."""
    docs = [_tokenize(name) for name in product_names]
    df: Counter = Counter()
    for doc in docs:
        for word in set(doc):
            df[word] += 1

    n = len(docs)
    vectors = []
    for doc in docs:
        if not doc:
            vectors.append({})
            continue
        tf = Counter(doc)
        vec = {
            w: (c / len(doc)) * math.log((n + 1) / (df[w] + 1)) + 1e-9
            for w, c in tf.items()
        }
        vectors.append(vec)
    return vectors


def cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    if not v1 or not v2:
        return 0.0
    common = set(v1) & set(v2)
    dot = sum(v1[w] * v2[w] for w in common)
    norm1 = math.sqrt(sum(x ** 2 for x in v1.values()))
    norm2 = math.sqrt(sum(x ** 2 for x in v2.values()))
    return dot / (norm1 * norm2) if norm1 and norm2 else 0.0


def average_vector(vectors: list[dict[str, float]]) -> dict[str, float]:
    if not vectors:
        return {}
    total: dict[str, float] = {}
    for vec in vectors:
        for word, weight in vec.items():
            total[word] = total.get(word, 0.0) + weight
    return {w: val / len(vectors) for w, val in total.items()}


def subtract_vectors(v1: dict[str, float], v2: dict[str, float], weight: float = 0.5) -> dict[str, float]:
    """v1 - weight * v2, тільки по спільних та власних ключах v1."""
    result = dict(v1)
    for word, val in v2.items():
        result[word] = result.get(word, 0.0) - weight * val
    return result


# ---------------------------------------------------------------------------
# 3. Модель товару-кандидата
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    id: str
    name: str
    discount_percent: float          # знижка у % (0-100)
    category: str = field(init=False)

    def __post_init__(self) -> None:
        self.category = categorize_product(self.name)

    @classmethod
    def from_product(cls, product: object) -> "Candidate":
        """Адаптер з core.mcp_client.Product (має .mcp_id/.name/.discount_percent)."""
        return cls(
            id=str(product.mcp_id),  # type: ignore[attr-defined]
            name=product.name,  # type: ignore[attr-defined]
            discount_percent=float(product.discount_percent),  # type: ignore[attr-defined]
        )


# ---------------------------------------------------------------------------
# 4. Історія угод групи (для профілю)
# ---------------------------------------------------------------------------

@dataclass
class DealHistoryRecord:
    product_name: str
    status: str              # "confirmed" | "expired" | "collecting" | ...
    participants_count: int


IGNORE_THRESHOLD_PARTICIPANTS = 3     # менше цієї к-сті = "проігнорували"
IGNORE_STREAK_TO_PENALIZE = 3         # карати категорію тільки після N ігнорів поспіль


def build_group_profile(
    history: list[DealHistoryRecord],
) -> tuple[dict[str, float], dict[str, int]]:
    """Повертає (profile_vector, category_scores).
    category_scores: {"молочка": +2, "солодке": -3, ...}
    Позитив: +1 за кожну confirmed угоду в категорії.
    Негатив: -1 за кожну expired угоду з participants_count < IGNORE_THRESHOLD,
             але тільки якщо це вже не перший ігнор поспіль для категорії.
    """
    positive_names: list[str] = []
    negative_names: list[str] = []
    category_scores: dict[str, int] = {}
    category_ignore_streak: dict[str, int] = {}

    for record in history:
        category = categorize_product(record.product_name)

        if record.status == "confirmed":
            positive_names.append(record.product_name)
            category_scores[category] = category_scores.get(category, 0) + 1
            category_ignore_streak[category] = 0  # скидаємо streak ігнорів

        elif record.status == "expired" and record.participants_count < IGNORE_THRESHOLD_PARTICIPANTS:
            streak = category_ignore_streak.get(category, 0) + 1
            category_ignore_streak[category] = streak
            if streak >= IGNORE_STREAK_TO_PENALIZE:
                negative_names.append(record.product_name)
                category_scores[category] = category_scores.get(category, 0) - 1

    positive_vec = average_vector(tf_idf_vectors(positive_names)) if positive_names else {}
    negative_vec = average_vector(tf_idf_vectors(negative_names)) if negative_names else {}
    profile_vector = subtract_vectors(positive_vec, negative_vec, weight=0.5)

    return profile_vector, category_scores


# ---------------------------------------------------------------------------
# 5. Вибір товарів на день: exploit (топ за рахунком) + explore (недопопулярна категорія)
# ---------------------------------------------------------------------------

DAILY_POST_LIMIT = 5
EXPLORE_SLOTS = 1     # скільки місць з DAILY_POST_LIMIT гарантовано під explore


def rank_products_for_group(
    products: list[Candidate],
    history: list[DealHistoryRecord] | None = None,
    daily_limit: int = DAILY_POST_LIMIT,
    explore_slots: int = EXPLORE_SLOTS,
) -> list[Candidate]:
    """Головна функція (чиста). Повертає список товарів для постингу цій групі.

    history=None або порожня історія = cold start: просто топ за знижкою.

    Добірка не дає одній категорії зайняти весь батч (жодна категорія не
    отримує більше половини публікацій), а вільні місця дозаповнюються
    категоріями, які група раніше ігнорувала (explore).
    """
    if not products:
        return []

    profile_vector, category_scores = build_group_profile(history or [])

    # --- COLD START: історії немає взагалі -> топ за знижкою (з розподілом по категоріях) ---
    if not profile_vector and not category_scores:
        ranked = sorted(products, key=lambda p: p.discount_percent, reverse=True)
        return _diversify([(p, float(p.discount_percent)) for p in ranked], daily_limit)

    # --- Рахуємо релевантність для кожного товару ---
    names = [p.name for p in products]
    product_vectors = tf_idf_vectors(names)

    scored: list[tuple[Candidate, float]] = []
    for product, vec in zip(products, product_vectors):
        similarity = cosine_sim(profile_vector, vec)
        discount_component = product.discount_percent / 100
        score = 0.7 * similarity + 0.3 * discount_component
        scored.append((product, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)

    picks = _diversify(scored, daily_limit)
    return _add_explore(picks, scored, category_scores, explore_slots, daily_limit)


def _diversify(scored: list[tuple[Candidate, float]], daily_limit: int) -> list[Candidate]:
    """Обирає топ за рахунком, але не дає одній категорії зайняти весь батч:
    якщо категорій більше однієї — максимум половина батчу на категорію."""
    if not scored or daily_limit <= 0:
        return []
    categories = {product.category for product, _ in scored}
    cap = daily_limit
    if len(categories) > 1:
        cap = max(1, math.ceil(daily_limit / 2))
    counts: dict[str, int] = {}
    picks: list[Candidate] = []
    for product, _score in scored:
        if len(picks) >= daily_limit:
            break
        if counts.get(product.category, 0) >= cap:
            continue
        counts[product.category] = counts.get(product.category, 0) + 1
        picks.append(product)
    return picks


def _add_explore(
    picks: list[Candidate],
    scored: list[tuple[Candidate, float]],
    category_scores: dict[str, int],
    explore_slots: int,
    daily_limit: int,
) -> list[Candidate]:
    """Дозаповнює вільні місця категоріями, які група найчастіше ігнорувала."""
    if explore_slots <= 0 or len(picks) >= daily_limit:
        return picks
    for cat in set(CATEGORY_KEYWORDS.keys()):
        category_scores.setdefault(cat, 0)
    picked_cats = {p.category for p in picks}
    picked_ids = {p.id for p in picks}
    slots_left = daily_limit - len(picks)
    for category, _score in sorted(category_scores.items(), key=lambda kv: kv[1]):
        if slots_left <= 0 or explore_slots <= 0:
            break
        if category in picked_cats:
            continue
        candidates = [
            p for p, _ in scored
            if p.category == category and p.id not in picked_ids
        ]
        if not candidates:
            continue
        best = max(candidates, key=lambda p: p.discount_percent)
        picks.append(best)
        picked_ids.add(best.id)
        picked_cats.add(category)
        slots_left -= 1
        explore_slots -= 1
    return picks


# ---------------------------------------------------------------------------
# 6. Інтеграція з БД (SQLAlchemy)
# ---------------------------------------------------------------------------

async def get_group_deal_history(session: "AsyncSession", group_id: int) -> list[DealHistoryRecord]:
    """SELECT product_name, status, COUNT(participants) FROM deals WHERE group_id = :id"""
    from db.models import Deal, Participant

    query = (
        select(
            Deal.product_name,
            Deal.status,
            func.count(Participant.id),
        )
        .outerjoin(Participant, Participant.deal_id == Deal.id)
        .where(Deal.group_id == group_id)
        .group_by(Deal.id)
    )
    rows = (await session.execute(query)).all()
    return [
        DealHistoryRecord(
            product_name=name,
            status=str(status.value if hasattr(status, "value") else status),
            participants_count=int(count),
        )
        for name, status, count in rows
    ]


async def pick_products_for_group(
    session: "AsyncSession",
    group_id: int,
    products: list[object],
    daily_limit: int = DAILY_POST_LIMIT,
    explore_slots: int = EXPLORE_SLOTS,
) -> list[object]:
    """Рангована добірка товарів для групи. Повертає ті самі об'єкти Product."""
    history = await get_group_deal_history(session, group_id)
    candidates = [Candidate.from_product(p) for p in products]
    picks = rank_products_for_group(candidates, history, daily_limit, explore_slots)
    picked_ids = {p.id for p in picks}
    return [p for p in products if p.mcp_id in picked_ids]


def _demo() -> None:
    """Демо — можна запустити напряму: python core/relevance_scorer.py"""
    history = [
        DealHistoryRecord("Кава мелена Lavazza", "confirmed", 12),
        DealHistoryRecord("Чай чорний Ahmad", "confirmed", 9),
        DealHistoryRecord("Молоко Молокія 2.5%", "expired", 1),
        DealHistoryRecord("Кефір Яготинський", "expired", 2),
        DealHistoryRecord("Сметана Галичина", "expired", 0),
    ]

    candidates = [
        Candidate("p1", "Масло вершкове Яготинське 200г", discount_percent=22),
        Candidate("p2", "Сир твердий Голландський", discount_percent=15),
        Candidate("p3", "Гречка ядриця Сільпо 1кг", discount_percent=30),
        Candidate("p4", "Курка охолоджена гомілка", discount_percent=18),
        Candidate("p5", "Шоколад молочний Milka", discount_percent=25),
        Candidate("p6", "Скумбрія копчена", discount_percent=12),
        Candidate("p7", "Кава мелена Jacobs", discount_percent=10),
        Candidate("p8", "Йогурт питний Активіа", discount_percent=20),
    ]

    picks = rank_products_for_group(candidates, history, daily_limit=5, explore_slots=1)

    print("Обрано для постингу сьогодні:")
    for p in picks:
        print(f"  [{p.category:8}] {p.name} (знижка {p.discount_percent}%)")


if __name__ == "__main__":
    _demo()
