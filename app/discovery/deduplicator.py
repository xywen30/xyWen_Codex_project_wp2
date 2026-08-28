from __future__ import annotations

from app.models import SearchResult
from .normalizer import canonicalize_ozon_url, stable_product_key


def deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    best: dict[tuple[str, str, str, str, str], SearchResult] = {}
    for row in results:
        row.canonical_url = canonicalize_ozon_url(row.url)
        if not row.canonical_url:
            continue
        row.product_id = stable_product_key(row.canonical_url)
        # REAL 与 DEMO 必须隔离，避免同一商品的演示快照覆盖真实快照。
        # 同一天同来源去重，但必须保留跨日期历史快照，供 7/15 天趋势计算。
        key = (row.data_source, row.product_id, row.engine, row.keyword, row.collected_at[:10])
        if key not in best or row.rank < best[key].rank:
            best[key] = row
    return list(best.values())
