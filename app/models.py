from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    engine: str
    keyword: str
    category: str
    rank: int
    title: str
    url: str
    snippet: str
    collected_at: str
    data_source: str = "REAL"
    product_id: Optional[str] = None
    canonical_url: Optional[str] = None
    price_rub: Optional[float] = None
    original_price_rub: Optional[float] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    brand: Optional[str] = None
    seller: Optional[str] = None
    source_url: Optional[str] = None
    raw_snippet: Optional[str] = None


@dataclass
class SourceDiagnostic:
    source: str
    status: str
    http_status: Optional[int]
    content_type: str
    elapsed_ms: int
    result_count: int
    ozon_url_count: int
    blocked_reason: str
    tested_at: str
    request_url: str
