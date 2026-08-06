from core.relevance_scorer import (
    Candidate,
    DealHistoryRecord,
    build_group_profile,
    categorize_product,
    cosine_sim,
    rank_products_for_group,
    tf_idf_vectors,
)


def test_categorize_product():
    assert categorize_product("Масло вершкове Яготинське 200г") == "масло"
    assert categorize_product("Олія соняшникова 850мл") == "масло"
    assert categorize_product("Гречка ядриця Сільпо 1кг") == "каші"
    assert categorize_product("Курка охолоджена гомілка") == "м'ясо"
    assert categorize_product("Шоколад молочний Milka") == "солодке"
    assert categorize_product("Оселедець слабосолений") == "риба"
    assert categorize_product("Пральний порошок 2кг") == "інше"


def test_tfidf_cosine():
    names = ["молоко 2.5%", "кефір 2.5%", "шоколад"]
    vectors = tf_idf_vectors(names)
    assert cosine_sim(vectors[0], vectors[0]) > 0.99
    assert cosine_sim(vectors[0], vectors[1]) > 0
    assert cosine_sim(vectors[0], vectors[2]) == 0.0


def test_build_group_profile_positive_and_negative():
    history = [
        DealHistoryRecord("Молоко Молокія 2.5%", "confirmed", 12),
        DealHistoryRecord("Масло вершкове", "confirmed", 9),
        DealHistoryRecord("Гречка ядриця", "expired", 1),
        DealHistoryRecord("Рис довгозернистий", "expired", 0),
        DealHistoryRecord("Вівсянка швидкого приготування", "expired", 0),
    ]
    profile_vector, category_scores = build_group_profile(history)
    assert profile_vector
    assert category_scores["молочка"] == 1
    assert category_scores["масло"] == 1
    # 3 ігнори поспіль у "каші" -> штраф
    assert category_scores["каші"] == -1


def test_build_group_profile_single_ignore_not_penalized():
    history = [
        DealHistoryRecord("Гречка ядриця", "expired", 1),
    ]
    _profile_vector, category_scores = build_group_profile(history)
    assert "каші" not in category_scores or category_scores["каші"] == 0


def test_rank_cold_start_top_by_discount():
    products = [
        Candidate("p1", "Масло вершкове", discount_percent=50),
        Candidate("p2", "Гречка ядриця", discount_percent=60),
        Candidate("p3", "Шоколад", discount_percent=55),
    ]
    picks = rank_products_for_group(products, history=[], daily_limit=5, explore_slots=0)
    assert [p.id for p in picks] == ["p2", "p3", "p1"]


def test_rank_no_history_arg_is_cold_start():
    products = [
        Candidate("p1", "Масло вершкове", discount_percent=50),
        Candidate("p2", "Гречка ядриця", discount_percent=60),
    ]
    picks = rank_products_for_group(products, history=None, daily_limit=2, explore_slots=0)
    assert [p.id for p in picks] == ["p2", "p1"]


def test_rank_respects_daily_limit():
    products = [Candidate(f"p{i}", f"Товар тест {i}", discount_percent=50 + i) for i in range(10)]
    picks = rank_products_for_group(products, history=[], daily_limit=3, explore_slots=0)
    assert len(picks) == 3


def test_rank_explore_reserves_slot_for_ignored_category():
    products = [
        Candidate("c1", "Курка охолоджена філе", discount_percent=10),
        Candidate("c2", "Молоко Молокія 2.5%", discount_percent=12),
        Candidate("c3", "Гречка ядриця Сільпо 1кг", discount_percent=70),
    ]
    history = [
        # каші тричі ігнорували -> штраф, має потрапити в explore-слот
        DealHistoryRecord("Гречка ядриця", "expired", 0),
        DealHistoryRecord("Рис довгозернистий", "expired", 1),
        DealHistoryRecord("Вівсянка швидка", "expired", 0),
        DealHistoryRecord("Молоко Молокія", "confirmed", 10),
    ]
    picks = rank_products_for_group(products, history=history, daily_limit=2, explore_slots=1)
    picked_categories = {p.category for p in picks}
    assert "каші" in picked_categories


def test_candidate_from_product_adapter():
    class FakeProduct:
        mcp_id = "abc"
        name = "Олія соняшникова 850мл"
        discount_percent = 55.0

    cand = Candidate.from_product(FakeProduct())
    assert cand.id == "abc"
    assert cand.category == "масло"
    assert cand.discount_percent == 55.0
