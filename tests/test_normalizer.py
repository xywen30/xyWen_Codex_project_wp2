from app.discovery.normalizer import canonicalize_ozon_url,extract_product_id

def test_normalizer_removes_tracking_and_extracts_id():
    url="https://ozon.ru/product/towel-123456789/?utm_source=x&foo=y"
    assert canonicalize_ozon_url(url)=="https://www.ozon.ru/product/towel-123456789/"
    assert extract_product_id(url)=="123456789"

def test_non_ozon_is_rejected(): assert canonicalize_ozon_url("https://example.com/product/123456") == ""
