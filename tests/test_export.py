import csv

from app.services.export_service import export_rankings


def _row(index: int) -> dict:
    return {
        "product_id": str(index), "metric_date": "2026-08-19", "title": f"商品{index}", "title_cn": f"中文商品{index}",
        "url": f"https://www.ozon.ru/product/item-{100000 + index}/", "category": "家纺", "category_level_1": "家纺", "category_level_2": "床品",
        "first_seen_at": "2026-08-17", "last_seen_at": "2026-08-19", "trend_score": index, "breakout_score": index,
        "potential_score": index, "base_potential_score": index - 1, "combined_analysis_score": index, "confidence_score": 30 + index,
        "data_source": "REAL", "rub_cny": .08, "exchange_rate_date": "2026-08-19", "exchange_rate_source": "CBR",
        "review_status": "available", "review_count": index * 10, "review_count_total": index * 10, "reviews_7d": index,
        "reviews_15d": index, "reviews_30d": index, "review_heat_score": index, "review_heat_level": "中", "review_reason": "公开快照增长",
        "review_risk": "不代表销量", "review_confidence": "中", "review_source": "public", "search_sources": "public",
    }


def test_export_top20_is_unique_and_new_outputs_exist(tmp_path):
    rows = [_row(index) for index in range(1, 26)] + [_row(25)]
    result = export_rankings(tmp_path, rows, {"history_days": 3, "metric_date": "2026-08-19"}, "REAL")
    potential_path = tmp_path / "data" / "exports" / "top20_potential_20260819_real.csv"
    with potential_path.open("r", encoding="utf-8-sig", newline="") as handle:
        potential_rows = list(csv.DictReader(handle))
    assert result["potential"] == 20
    assert len(potential_rows) == len({row["商品ID/SKU"] for row in potential_rows}) == 20
    assert (tmp_path / "data" / "exports" / "review_heat_preanalysis_20260819_real.csv").exists()
    assert (tmp_path / "data" / "exports" / "home_category_diagnostics_20260819_real.csv").exists()
    full = (tmp_path / "data" / "exports" / "ozon_home_trend_analysis_20260819_real.csv").read_bytes()
    assert full.startswith(b"\xef\xbb\xbf")
    assert "商品名称_中文名称" in full.decode("utf-8-sig")


def test_potential_top20_prefers_category_diversity(tmp_path):
    categories = ["厨房用品", "收纳整理", "家居装饰", "灯具照明", "浴室用品", "清洁用品", "家纺", "家具/置物用品", "花园园艺", "创意家居/生活用品"]
    rows = []
    for index in range(1, 31):
        row = _row(index)
        row["potential_score"] = 1000 - index
        rows.append(row)
    for category_index, category in enumerate(categories):
        for offset in range(2):
            index = 100 + category_index * 2 + offset
            row = _row(index)
            row["category"] = category
            row["category_level_1"] = category
            row["potential_score"] = 100 - index
            row["review_status"] = "not_selected"
            rows.append(row)
    export_rankings(tmp_path, rows, {"history_days": 3, "metric_date": "2026-08-19"}, "REAL")
    potential_path = tmp_path / "data" / "exports" / "top20_potential_20260819_real.csv"
    with potential_path.open("r", encoding="utf-8-sig", newline="") as handle:
        potential_rows = list(csv.DictReader(handle))
    counts = {}
    for row in potential_rows:
        counts[row["一级类目"]] = counts.get(row["一级类目"], 0) + 1
    assert len(potential_rows) == 20
    assert len(counts) == 10
    assert set(row["一级类目"] for row in potential_rows[:10]) == set(categories)
    assert max(counts.values()) <= 2
