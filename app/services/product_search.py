from __future__ import annotations

import pandas as pd


def filter_products(
    frame: pd.DataFrame,
    keyword: str = "",
    categories: list[str] | None = None,
    heat_min: float = 0,
    potential_min: float = 0,
    price_min: float | None = None,
    price_max: float | None = None,
    review_min: int = 0,
    date_from=None,
    date_to=None,
) -> pd.DataFrame:
    """Apply lightweight local filters without making any network requests."""
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    if keyword.strip():
        searchable = [column for column in ("title", "title_cn", "category", "category_level_1", "category_level_2", "product_id", "search_keywords") if column in result]
        mask = pd.Series(False, index=result.index)
        for column in searchable:
            mask |= result[column].fillna("").astype(str).str.contains(keyword.strip(), case=False, regex=False)
        result = result[mask]
    if categories:
        category_column = "category_level_1" if "category_level_1" in result else "category"
        if category_column in result:
            result = result[result[category_column].isin(categories)]
    numeric_filters = (
        ("review_heat_score", heat_min, ">="),
        ("potential_score", potential_min, ">="),
        ("price_rub", price_min, ">="),
        ("price_rub", price_max, "<="),
        ("review_count", review_min, ">="),
    )
    for column, value, operator in numeric_filters:
        if value is None or column not in result:
            continue
        numbers = pd.to_numeric(result[column], errors="coerce")
        result = result[numbers >= value] if operator == ">=" else result[numbers <= value]
    date_column = next((column for column in ("metric_date", "last_seen_at", "snapshot_date") if column in result), None)
    if date_column:
        dates = pd.to_datetime(result[date_column], errors="coerce")
        if date_from is not None:
            result = result[dates >= pd.Timestamp(date_from)]
            dates = pd.to_datetime(result[date_column], errors="coerce")
        if date_to is not None:
            result = result[dates <= pd.Timestamp(date_to)]
    return result
