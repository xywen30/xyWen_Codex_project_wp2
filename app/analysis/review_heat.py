from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import ceil, log10


def _as_date(value: object) -> date:
    return date.fromisoformat(str(value)[:10])


def _window_delta(observations: list[tuple[date, int]], metric_date: date, days: int) -> int | None:
    cutoff = metric_date - timedelta(days=days - 1)
    points = [(day, count) for day, count in observations if cutoff <= day <= metric_date]
    if len(points) < 2:
        return None
    return max(0, points[-1][1] - points[0][1])


def calculate_review_heat(rows: list[dict], metric_date: date | str) -> dict:
    metric_day = _as_date(metric_date)
    by_day: dict[date, list[int]] = defaultdict(list)
    rating_by_day: dict[date, list[float]] = defaultdict(list)
    sources: set[str] = set()
    for row in rows:
        if row.get("review_count") is not None:
            by_day[_as_date(row.get("snapshot_date") or row.get("collected_at"))].append(max(0, int(row["review_count"])))
        if row.get("rating") is not None:
            rating_by_day[_as_date(row.get("snapshot_date") or row.get("collected_at"))].append(float(row["rating"]))
        if row.get("engine"):
            sources.add(str(row["engine"]))
    observations = sorted((day, max(values)) for day, values in by_day.items() if day <= metric_day)
    if not observations:
        return {
            "review_status": "unavailable",
            "review_count_total": None,
            "review_heat_score": None,
            "review_heat_level": "低",
            "review_reason": "公开数据源未提供可用评论数量",
            "review_risk": "评论数据不可用；未抓取 Ozon 评论页，商品基础数据仍保留",
            "review_source": "、".join(sorted(sources)),
            "review_confidence": "数据不足",
        }

    latest_day, total_reviews = observations[-1]
    rating = None
    for day in sorted(rating_by_day, reverse=True):
        if day <= metric_day and rating_by_day[day]:
            rating = max(rating_by_day[day])
            break
    delta7 = _window_delta(observations, metric_day, 7)
    delta15 = _window_delta(observations, metric_day, 15)
    delta30 = _window_delta(observations, metric_day, 30)
    growth_days = [current_day for (previous_day, previous), (current_day, current) in zip(observations, observations[1:]) if current > previous]
    last_growth_day = growth_days[-1] if growth_days else None
    days_since_growth = (metric_day - last_growth_day).days if last_growth_day else None
    intervals = max(0, len(observations) - 1)
    continuity = len(growth_days) / intervals if intervals else 0.0

    total_component = min(20.0, log10(total_reviews + 1) / 5 * 20)
    recent7_component = min(35.0, log10(max(0, delta7 or 0) + 1) / 3 * 35)
    recent15_component = min(15.0, log10(max(0, delta15 or 0) + 1) / 3.5 * 15)
    recent30_component = min(10.0, log10(max(0, delta30 or 0) + 1) / 4 * 10)
    recency_component = 0.0
    if days_since_growth is not None:
        recency_component = 10.0 if days_since_growth <= 1 else (8.0 if days_since_growth <= 7 else (5.0 if days_since_growth <= 15 else (3.0 if days_since_growth <= 30 else 0.0)))
    rating_component = 0.0 if rating is None else max(0.0, min(10.0, (rating - 3.5) / 1.5 * 10))
    score = round(min(100.0, total_component + recent7_component + recent15_component + recent30_component + recency_component + rating_component), 2)
    level = "高" if score >= 75 else ("中高" if score >= 60 else ("中" if score >= 40 else "低"))

    reasons = []
    if delta7:
        reasons.append(f"最近7天公开快照评论数增加{delta7}")
    elif delta30:
        reasons.append(f"最近30天公开快照评论数增加{delta30}")
    elif total_reviews >= 1000:
        reasons.append("历史累计评论基数较高，但近期快照未观察到增长")
    else:
        reasons.append("近期公开快照未观察到明确评论数增长")
    if last_growth_day:
        reasons.append(f"最近一次评论数增长观测距今{days_since_growth}天")
    if rating is not None and rating >= 4.7:
        reasons.append(f"公开评分{rating:.1f}")

    return {
        "review_status": "available" if len(observations) >= 2 else "partial",
        "review_count_total": total_reviews,
        "latest_review_time": None,
        "days_since_latest_review": None,
        "review_growth_observed_at": last_growth_day.isoformat() if last_growth_day else None,
        "days_since_review_growth": days_since_growth,
        "reviews_7d": delta7,
        "reviews_15d": delta15,
        "reviews_30d": delta30,
        "review_activity": round(continuity * 100, 2),
        "review_observation_span_days": (observations[-1][0] - observations[0][0]).days + 1,
        "review_heat_score": score,
        "review_heat_level": level,
        "review_reason": " + ".join(reasons),
        "review_risk": "公开源不含单条评论日期；7/15/30天为评论总数快照增量代理，不代表销量或订单数",
        "review_source": "、".join(sorted(sources)),
        "review_confidence": "高" if len(observations) >= 5 else ("中" if len(observations) >= 2 else "数据不足"),
        "latest_review_observation_date": latest_day.isoformat(),
    }


def build_review_heat_map(snapshots: list[dict], metric_date: date | str, product_ids: set[str] | None = None) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in snapshots:
        product_id = str(row.get("product_id"))
        if product_ids is None or product_id in product_ids:
            grouped[product_id].append(row)
    return {product_id: calculate_review_heat(rows, metric_date) for product_id, rows in grouped.items()}


def apply_review_heat(rows: list[dict], snapshots: list[dict], metric_date: date | str, max_candidates: int = 100, min_candidates: int = 50) -> tuple[list[dict], dict]:
    if not rows:
        return rows, {"candidate_count": 0, "success_count": 0, "unavailable_count": 0}
    target = min(len(rows), max_candidates, max(min_candidates, ceil(len(rows) * 0.6)))
    ranked = sorted(rows, key=lambda row: (row.get("potential_score") or 0, row.get("confidence_score") or 0), reverse=True)
    selected_ids: set[str] = set()
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in ranked:
        category = str(row.get("category_level_1") or row.get("category") or "未分类")
        by_category[category].append(row)
    for category_rows in by_category.values():
        for row in category_rows[:2]:
            if len(selected_ids) >= target:
                break
            selected_ids.add(str(row["product_id"]))
    for row in ranked:
        if len(selected_ids) >= target:
            break
        selected_ids.add(str(row["product_id"]))
    heat_map = build_review_heat_map(snapshots, metric_date, selected_ids)
    success = unavailable = 0
    for row in rows:
        base = float(row.get("potential_score") or 0)
        row["base_potential_score"] = round(base, 2)
        product_id = str(row["product_id"])
        if product_id not in selected_ids:
            row.update(review_status="not_selected", review_heat_score=None, review_heat_level="低", combined_analysis_score=round(base, 2))
            continue
        review = heat_map.get(product_id) or calculate_review_heat([], metric_date)
        row.update(review)
        if review.get("review_heat_score") is None:
            unavailable += 1
            row["combined_analysis_score"] = round(base, 2)
        else:
            success += 1
            row["combined_analysis_score"] = round(0.85 * base + 0.15 * float(review["review_heat_score"]), 2)
            row["potential_score"] = row["combined_analysis_score"]
    selected_categories = {
        str(row.get("category_level_1") or row.get("category") or "未分类")
        for row in rows
        if str(row.get("product_id")) in selected_ids
    }
    return rows, {"candidate_count": target, "success_count": success, "unavailable_count": unavailable, "categories_covered": len(selected_categories)}
