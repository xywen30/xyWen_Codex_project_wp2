from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


@lru_cache(maxsize=4)
def load_home_categories(root: str | Path = ROOT) -> list[dict]:
    path = Path(root) / "config" / "home_category_config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_search_keywords(categories: list[dict]) -> list[dict]:
    output: list[dict] = []
    for category in categories:
        for keyword in category.get("keywords_ru", []):
            output.append(
                {
                    "keyword": keyword,
                    "category_cn": category["category_cn"],
                    "category_id": category["category_id"],
                    "category_ru": category.get("keywords_ru", [""])[0],
                    "enabled": True,
                }
            )
    return output


def balanced_search_keywords(keywords: list[dict], per_category: int = 1, max_total: int = 10) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for item in keywords:
        if not item.get("enabled", True):
            continue
        key = str(item.get("category_id") or item.get("category_cn") or "other")
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(item)
    output: list[dict] = []
    for offset in range(max(1, per_category)):
        for key in order:
            if offset < len(grouped[key]):
                output.append(grouped[key][offset])
                if len(output) >= max_total:
                    return output
    return output


def classify_home_category(
    title: object,
    query: object = "",
    fallback: object = "创意家居/生活用品",
    categories: list[dict] | None = None,
) -> dict[str, str]:
    categories = categories or load_home_categories()
    title_text = _normalize(title)
    query_text = _normalize(query)
    matches: list[tuple[int, int, dict, str]] = []
    for category_index, category in enumerate(categories):
        terms = []
        for key in ("keywords_ru", "keywords_zh", "keywords_en"):
            terms.extend(str(item) for item in category.get(key, []))
        for term in sorted({_normalize(item) for item in terms if item}, key=len, reverse=True):
            if term and term in query_text:
                matches.append((2, len(term), category, term))
            elif term and term in title_text:
                matches.append((1, len(term), category, term))
    if matches:
        _, _, category, term = max(matches, key=lambda item: (item[0], item[1], -categories.index(item[2])))
        return {
            "category_id": str(category["category_id"]),
            "category_level_1": str(category["category_cn"]),
            "category_level_2": term,
        }
    fallback_text = _normalize(fallback)
    for category in categories:
        if _normalize(category.get("category_cn")) == fallback_text:
            return {
                "category_id": str(category["category_id"]),
                "category_level_1": str(category["category_cn"]),
                "category_level_2": query_text or "未细分",
            }
    return {"category_id": "creative_living", "category_level_1": "创意家居/生活用品", "category_level_2": query_text or "未细分"}
