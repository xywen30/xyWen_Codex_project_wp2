from app.category_config import balanced_search_keywords, classify_home_category, flatten_search_keywords, load_home_categories


def test_home_matrix_has_ten_balanced_categories():
    categories = load_home_categories()
    assert len(categories) == 10
    assert all(5 <= len(item["keywords_ru"]) <= 15 for item in categories)
    selected = balanced_search_keywords(flatten_search_keywords(categories), per_category=1, max_total=10)
    assert len(selected) == 10
    assert len({item["category_cn"] for item in selected}) == 10


def test_home_classifier_maps_core_public_products():
    assert classify_home_category("Комплект постельного белья")["category_level_1"] == "家纺"
    assert classify_home_category("Полотенце махровое")["category_level_1"] == "浴室用品"
    assert classify_home_category("Гель для стирки")["category_level_1"] == "清洁用品"
    assert classify_home_category("Storage box organizer")["category_level_1"] == "收纳整理"
