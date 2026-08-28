from __future__ import annotations

import json
from pathlib import Path

from app.category_config import load_home_categories
from app.discovery.normalizer import canonicalize_ozon_url, extract_product_id
from app.models import SearchResult


class PublicSearchIndexSnapshotSource:
    """Load a dated, auditable snapshot captured from public search result snippets."""

    def __init__(self, root: Path, snapshot_name: str = "public_search_index_snapshot_20260819.json"):
        self.root = Path(root)
        self.path = self.root / "config" / snapshot_name
        self.last_status = "NOT_RUN"
        self.limitations = ""

    def discover_all(self) -> list[SearchResult]:
        if not self.path.exists():
            self.last_status = "MISSING"
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        observed_at = str(payload.get("observed_at") or "")
        source_name = str(payload.get("source_name") or "public_web_index")
        method = str(payload.get("method") or "公开搜索索引结果摘要")
        self.limitations = str(payload.get("limitations") or "索引摘要可能滞后")
        valid_categories = {item["category_cn"] for item in load_home_categories(self.root)}
        output: list[SearchResult] = []
        for item in payload.get("rows", []):
            category = str(item.get("category") or "")
            url = canonicalize_ozon_url(str(item.get("url") or ""))
            product_id = extract_product_id(url)
            if category not in valid_categories or not url or not product_id or not observed_at:
                continue
            if str(item.get("product_id") or product_id) != product_id:
                continue
            crawl_label = str(item.get("index_crawled_label") or "未提供")
            snippet = f"{method}；索引抓取时间标签={crawl_label}；{self.limitations}"
            output.append(
                SearchResult(
                    engine=source_name,
                    keyword=str(item.get("keyword") or "公开搜索索引"),
                    category=category,
                    rank=max(1, int(item.get("rank") or 999)),
                    title=str(item.get("title") or "Ozon 商品"),
                    url=url,
                    snippet=snippet,
                    collected_at=observed_at,
                    data_source="REAL",
                    product_id=product_id,
                    canonical_url=url,
                    price_rub=float(item["price_rub"]) if item.get("price_rub") is not None else None,
                    original_price_rub=float(item["original_price_rub"]) if item.get("original_price_rub") is not None else None,
                    rating=float(item["rating"]) if item.get("rating") is not None else None,
                    review_count=int(item["review_count"]) if item.get("review_count") is not None else None,
                    source_url=url,
                    raw_snippet=snippet,
                )
            )
        self.last_status = "SUCCESS" if output else "EMPTY"
        return output
