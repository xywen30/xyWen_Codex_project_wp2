from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit


PRODUCT_ID_PATTERNS = [re.compile(r"-(\d{6,})(?:/|$)"), re.compile(r"/product/(\d{6,})(?:/|$)")]


def extract_product_id(url: str) -> str | None:
    clean = canonicalize_ozon_url(url)
    for pattern in PRODUCT_ID_PATTERNS:
        match = pattern.search(clean)
        if match:
            return match.group(1)
    return None


def canonicalize_ozon_url(url: str) -> str:
    value = (url or "").strip()
    if value.startswith("//"):
        value = "https:" + value
    parts = urlsplit(value)
    host = parts.netloc.lower().replace("www.ozon.ru", "ozon.ru")
    if host not in {"ozon.ru", "www.ozon.ru"}:
        return ""
    path = re.sub(r"/+", "/", parts.path).rstrip("/") + "/"
    return urlunsplit(("https", "www.ozon.ru", path, "", ""))


def stable_product_key(url: str) -> str:
    canonical = canonicalize_ozon_url(url)
    return extract_product_id(canonical) or hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
