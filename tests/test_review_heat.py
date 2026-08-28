from app.analysis.review_heat import apply_review_heat, calculate_review_heat


def test_recent_review_growth_beats_old_large_but_static_total():
    recent = [
        {"snapshot_date": "2026-08-12", "review_count": 50, "rating": 4.8, "engine": "public"},
        {"snapshot_date": "2026-08-19", "review_count": 150, "rating": 4.8, "engine": "public"},
    ]
    static = [
        {"snapshot_date": "2026-08-12", "review_count": 100000, "rating": 4.8, "engine": "public"},
        {"snapshot_date": "2026-08-19", "review_count": 100000, "rating": 4.8, "engine": "public"},
    ]
    recent_result = calculate_review_heat(recent, "2026-08-19")
    static_result = calculate_review_heat(static, "2026-08-19")
    assert recent_result["reviews_15d"] == 100
    assert recent_result["review_growth_observed_at"] == "2026-08-19"
    assert recent_result["review_heat_score"] > static_result["review_heat_score"]
    assert "不代表销量或订单数" in recent_result["review_risk"]


def test_review_candidate_selection_keeps_each_discovered_category():
    rows = []
    snapshots = []
    for category_index in range(10):
        for offset in range(6):
            product_id = str(category_index * 10 + offset)
            rows.append({
                "product_id": product_id,
                "category_level_1": f"类目{category_index}",
                "potential_score": 1000 - category_index * 100 - offset,
                "confidence_score": 50,
            })
            snapshots.append({
                "product_id": product_id,
                "snapshot_date": "2026-08-19",
                "review_count": offset + 1,
                "rating": 4.8,
                "engine": "public",
            })
    _, summary = apply_review_heat(rows, snapshots, "2026-08-19", max_candidates=50, min_candidates=50)
    assert summary["candidate_count"] == 50
    assert summary["categories_covered"] == 10
