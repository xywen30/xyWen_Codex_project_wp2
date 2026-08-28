import pandas as pd

from app.services.product_search import filter_products


def test_product_search_filters_chinese_category_and_heat():
    frame = pd.DataFrame([
        {"product_id": "1", "title": "Коробка", "title_cn": "收纳箱", "category_level_1": "收纳整理", "review_heat_score": 85, "potential_score": 70, "price_rub": 500, "review_count": 200},
        {"product_id": "2", "title": "Лампа", "title_cn": "台灯", "category_level_1": "灯具照明", "review_heat_score": 40, "potential_score": 80, "price_rub": 900, "review_count": 50},
    ])
    result = filter_products(frame, keyword="收纳", categories=["收纳整理"], heat_min=80)
    assert result.product_id.tolist() == ["1"]
