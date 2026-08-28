from app.services.translation_service import fallback_title_cn, translate_product_titles


def test_fallback_title_cn_is_readable_and_keeps_specs():
    translated = fallback_title_cn(
        "Порошок стиральный Автомат 15 кг концентрат Tide Колор, для цветного белья, 100 стирок",
        "стиральный порошок",
    )
    assert translated.startswith("洗衣粉")
    assert "Tide" in translated and "15公斤" in translated and "100次洗涤" in translated


def test_translation_service_does_not_need_network_for_chinese(tmp_path, monkeypatch):
    monkeypatch.setenv("OZON_TRANSLATION_REMOTE", "0")
    rows = [{"title": "纯棉毛巾", "search_keywords": "полотенце"}]
    result = translate_product_titles(tmp_path, rows, "REAL")
    assert rows[0]["title_cn"] == "纯棉毛巾"
    assert result["fallback"] == 0
