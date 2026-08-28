from __future__ import annotations

import csv
from collections import Counter
from datetime import date
from pathlib import Path

from app.category_config import load_home_categories


HEADERS = [
    "日期", "榜单排名", "数据性质", "商品ID/SKU", "商品名称", "商品名称_中文名称", "Ozon商品链接", "商品图片URL", "商品图片状态",
    "商品分类", "一级类目", "二级类目", "品牌", "卖家", "当前价格（卢布）", "原价（卢布）", "折扣率（%）", "当前价格（人民币估算）",
    "原价（人民币估算）", "RUB/CNY换算率", "汇率日期", "汇率来源", "评分", "评论数", "搜索来源", "搜索关键词", "当前公开列表排名",
    "Google当前排名", "Yandex当前排名", "Bing当前排名", "抓取时间", "来源页面", "首次发现日期", "最近发现日期", "7天排名变化", "15天排名变化",
    "排名速度", "前7天排名速度", "排名加速度", "关键词覆盖数", "关键词覆盖增长", "出现频率", "搜索引擎一致性", "搜索曝光代理指数（估算）",
    "爆品趋势指数（估算）", "爆发指数（估算）", "原潜力指数（估算）", "评论分析状态", "最近7天评论数增量（公开快照）",
    "最近15天评论数增量（公开快照）", "最近30天评论数增量（公开快照）", "评论热度评分（估算）", "评论热度预判", "综合潜力指数（估算）",
    "数据可信度分", "数据可信度", "建议关注等级", "推荐理由", "真实销量", "真实点击量", "真实停留时间", "是否进入7天TOP10", "是否进入15天TOP10",
    "是否进入潜力商品TOP20", "备注",
]

REVIEW_HEADERS = [
    "数据日期", "排名", "商品ID", "商品名称", "商品名称_中文名称", "一级类目", "二级类目", "商品链接", "商品图片", "当前价格RUB", "当前价格RMB",
    "商品评分", "总评论数", "最近评论时间", "距最近评论天数", "最近7天评论数增量（公开快照）", "最近15天评论数增量（公开快照）",
    "最近30天评论数增量（公开快照）", "评论活跃度（%）", "评论热度评分（估算）", "原潜力评分", "综合分析评分", "热门预判", "热门原因",
    "风险提示", "数据来源", "数据可信度", "采集时间",
]

DIAGNOSTIC_HEADERS = [
    "日期", "一级类目", "配置关键词数", "实际参与关键词数", "原始发现商品数", "去重后商品数", "有效商品数", "占比", "潜力TOP20入选数量",
    "评论热门商品数量", "数据来源数量", "异常说明",
]


def _unique_ranked(rows: list[dict], key) -> list[dict]:
    seen: set[str] = set()
    output: list[dict] = []
    for row in sorted(rows, key=key, reverse=True):
        product_id = str(row.get("product_id") or "")
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        output.append(row)
    return output


def _category_diverse_ranked(rows: list[dict], key, limit: int = 20, max_per_category: int = 3) -> list[dict]:
    """Prefer broad home-category coverage, then fill remaining slots by score."""
    ranked = _unique_ranked(rows, key)
    output: list[dict] = []
    selected: set[str] = set()
    grouped: dict[str, list[dict]] = {}
    for row in ranked:
        category = str(row.get("category_level_1") or row.get("category") or "未分类")
        grouped.setdefault(category, []).append(row)
    # Round-robin makes the first screen useful: first one item per category,
    # then a second item per category, instead of showing category blocks.
    for category_round in range(max_per_category):
        for category_rows in grouped.values():
            if category_round >= len(category_rows):
                continue
            row = category_rows[category_round]
            output.append(row)
            selected.add(str(row.get("product_id") or ""))
            if len(output) >= limit:
                return output
    for row in ranked:
        product_id = str(row.get("product_id") or "")
        if product_id in selected:
            continue
        output.append(row)
        selected.add(product_id)
        if len(output) >= limit:
            break
    return output


def _display(row: dict, rank: int, top7: set[str], top15: set[str], potential: set[str]) -> dict:
    product_id = str(row.get("product_id") or "")
    search_sources = str(row.get("search_sources") or "")
    source_note = "；公开搜索索引摘要可能滞后，未访问Ozon详情页复核" if "public_web_index" in search_sources else ""
    return {
        "日期": row.get("metric_date"), "榜单排名": rank,
        "数据性质": "真实公开数据" if row.get("data_source") == "REAL" else "演示数据",
        "商品ID/SKU": product_id, "商品名称": row.get("title"), "商品名称_中文名称": row.get("title_cn") or row.get("title"),
        "Ozon商品链接": row.get("url"), "商品图片URL": row.get("image_url"),
        "商品图片状态": "已获取真实图片地址" if row.get("image_url") else "公开源未提供真实图片，未生成或伪造",
        "商品分类": row.get("category"), "一级类目": row.get("category_level_1") or row.get("category"), "二级类目": row.get("category_level_2"),
        "品牌": row.get("brand") or "未获取", "卖家": row.get("seller") or "未获取",
        "当前价格（卢布）": row.get("price_rub"), "原价（卢布）": row.get("original_price_rub"), "折扣率（%）": row.get("discount_rate"),
        "当前价格（人民币估算）": row.get("price_cny"), "原价（人民币估算）": row.get("original_price_cny"), "RUB/CNY换算率": row.get("rub_cny"),
        "汇率日期": row.get("exchange_rate_date"), "汇率来源": row.get("exchange_rate_source"), "评分": row.get("rating"), "评论数": row.get("review_count"),
        "搜索来源": row.get("search_sources"), "搜索关键词": row.get("search_keywords"), "当前公开列表排名": row.get("current_rank"),
        "Google当前排名": row.get("google_rank"), "Yandex当前排名": row.get("yandex_rank"), "Bing当前排名": row.get("bing_rank"),
        "抓取时间": row.get("collected_at"), "来源页面": row.get("source_url"), "首次发现日期": str(row.get("first_seen_at") or "")[:10],
        "最近发现日期": str(row.get("last_seen_at") or "")[:10], "7天排名变化": row.get("rank_change_7d"), "15天排名变化": row.get("rank_change_15d"),
        "排名速度": row.get("rank_velocity_7d"), "前7天排名速度": row.get("rank_velocity_prev7"), "排名加速度": row.get("rank_acceleration"),
        "关键词覆盖数": row.get("keyword_coverage"), "关键词覆盖增长": row.get("keyword_coverage_growth"), "出现频率": row.get("presence_rate"),
        "搜索引擎一致性": row.get("engine_agreement_score"), "搜索曝光代理指数（估算）": row.get("visibility_score"),
        "爆品趋势指数（估算）": row.get("trend_score"), "爆发指数（估算）": row.get("breakout_score"), "原潜力指数（估算）": row.get("base_potential_score"),
        "评论分析状态": row.get("review_status"), "最近7天评论数增量（公开快照）": row.get("reviews_7d"),
        "最近15天评论数增量（公开快照）": row.get("reviews_15d"), "最近30天评论数增量（公开快照）": row.get("reviews_30d"),
        "评论热度评分（估算）": row.get("review_heat_score"), "评论热度预判": row.get("review_heat_level"),
        "综合潜力指数（估算）": row.get("combined_analysis_score", row.get("potential_score")), "数据可信度分": row.get("confidence_score"),
        "数据可信度": row.get("confidence_level"), "建议关注等级": row.get("recommendation_level"), "推荐理由": row.get("recommendation_reason"),
        "真实销量": "", "真实点击量": "", "真实停留时间": "",
        "是否进入7天TOP10": "是" if product_id in top7 else "否", "是否进入15天TOP10": "是" if product_id in top15 else "否",
        "是否进入潜力商品TOP20": "是" if product_id in potential else "否",
        "备注": "人民币金额按公开汇率估算；评论数变化和搜索曝光均为趋势代理，不代表真实销量、订单、点击或盈利" + source_note,
    }


def _review_display(row: dict, rank: int) -> dict:
    return {
        "数据日期": row.get("metric_date"), "排名": rank, "商品ID": str(row.get("product_id") or ""), "商品名称": row.get("title"),
        "商品名称_中文名称": row.get("title_cn") or row.get("title"), "一级类目": row.get("category_level_1") or row.get("category"),
        "二级类目": row.get("category_level_2"), "商品链接": row.get("url"), "商品图片": row.get("image_url"), "当前价格RUB": row.get("price_rub"),
        "当前价格RMB": row.get("price_cny"), "商品评分": row.get("rating"), "总评论数": row.get("review_count_total", row.get("review_count")),
        "最近评论时间": row.get("latest_review_time"), "距最近评论天数": row.get("days_since_latest_review"),
        "最近7天评论数增量（公开快照）": row.get("reviews_7d"), "最近15天评论数增量（公开快照）": row.get("reviews_15d"),
        "最近30天评论数增量（公开快照）": row.get("reviews_30d"), "评论活跃度（%）": row.get("review_activity"),
        "评论热度评分（估算）": row.get("review_heat_score"), "原潜力评分": row.get("base_potential_score"),
        "综合分析评分": row.get("combined_analysis_score"), "热门预判": row.get("review_heat_level"), "热门原因": row.get("review_reason"),
        "风险提示": row.get("review_risk"), "数据来源": row.get("review_source") or row.get("search_sources"),
        "数据可信度": row.get("review_confidence"), "采集时间": row.get("collected_at"),
    }


def _diagnostic_rows(root: Path, rows: list[dict], discovery: list[dict], potential: set[str], metric_date: str) -> list[dict]:
    try:
        category_items = load_home_categories(root)
    except FileNotFoundError:
        category_items = load_home_categories()
    configured = {item["category_cn"]: item for item in category_items}
    details = {str(item.get("category")): item for item in discovery}
    valid_counts = Counter(str(row.get("category_level_1") or row.get("category")) for row in rows)
    potential_counts = Counter(str(row.get("category_level_1") or row.get("category")) for row in rows if str(row.get("product_id")) in potential)
    hot_counts = Counter(str(row.get("category_level_1") or row.get("category")) for row in rows if row.get("review_heat_level") in {"高", "中高"})
    source_counts: dict[str, set[str]] = {name: set() for name in configured}
    keyword_counts: dict[str, set[str]] = {name: set() for name in configured}
    for row in rows:
        category = str(row.get("category_level_1") or row.get("category"))
        for source in str(row.get("search_sources") or "").split("、"):
            if source:
                source_counts.setdefault(category, set()).add(source)
        for keyword in str(row.get("search_keywords") or "").split("、"):
            if keyword:
                keyword_counts.setdefault(category, set()).add(keyword)
    total = sum(valid_counts.values())
    max_share = max(valid_counts.values(), default=0) / max(1, total)
    output = []
    for name, item in configured.items():
        found = details.get(name, {})
        count = valid_counts[name]
        notes = []
        rebuilt = not bool(found)
        if count == 0:
            notes.append("当前公开数据源未发现该类目有效商品")
        if max_share >= 0.60 and count == max(valid_counts.values(), default=0):
            notes.append("当前样本占比较高，存在类目偏斜风险")
        if rebuilt and count:
            notes.append("本次仅重跑分析，采集诊断由数据库现有快照重建")
        output.append({
            "日期": metric_date, "一级类目": name, "配置关键词数": len(item.get("keywords_ru", [])),
            "实际参与关键词数": found.get("attempted_keywords", len(keyword_counts.get(name, set()))),
            "原始发现商品数": found.get("raw_candidates", count),
            "去重后商品数": found.get("deduplicated_products", count), "有效商品数": count,
            "占比": round(count / total, 4) if total else 0, "潜力TOP20入选数量": potential_counts[name],
            "评论热门商品数量": hot_counts[name], "数据来源数量": max(found.get("source_count", 0), len(source_counts.get(name, set()))),
            "异常说明": "；".join(notes) if notes else "无明显异常",
        })
    return output


def write_csv(path: Path, rows: list[dict], headers: list[str] = HEADERS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_rankings(root: Path, rows: list[dict], meta: dict, source: str, discovery_diagnostics: list[dict] | None = None) -> dict:
    stamp = date.today().strftime("%Y%m%d")
    folder = root / "data" / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    eligible7 = meta["history_days"] >= 7 and sum(row.get("rank_velocity_7d") is not None for row in rows) >= 10
    eligible15 = meta["history_days"] >= 15 and sum(row.get("rank_acceleration") is not None for row in rows) >= 10
    unique_trend = _unique_ranked(rows, lambda row: (row.get("trend_score") or 0, row.get("visibility_score") or 0))
    potential_pool = rows
    top7_rows = unique_trend[:10] if eligible7 else []
    top15_rows = _unique_ranked(rows, lambda row: (row.get("breakout_score") or 0, row.get("trend_score") or 0))[:10] if eligible15 else []
    potential_rows = _category_diverse_ranked(
        potential_pool,
        lambda row: (
            int(row.get("review_status") not in {None, "not_selected"}),
            row.get("potential_score") or 0,
            row.get("confidence_score") or 0,
        ),
        limit=20,
        max_per_category=3,
    )
    review_rows = [row for row in _unique_ranked(rows, lambda row: (row.get("review_heat_score") or -1, row.get("potential_score") or 0)) if row.get("review_status") not in {None, "not_selected"}]
    top7 = {str(row["product_id"]) for row in top7_rows}
    top15 = {str(row["product_id"]) for row in top15_rows}
    potential = {str(row["product_id"]) for row in potential_rows}
    full = [_display(row, index + 1, top7, top15, potential) for index, row in enumerate(unique_trend)]
    diagnostics = _diagnostic_rows(root, rows, discovery_diagnostics or [], potential, str(meta["metric_date"]))
    files = {
        "all": folder / f"ozon_home_trend_analysis_{stamp}_{source.lower()}.csv",
        "top7": folder / f"top10_trend_7d_{stamp}_{source.lower()}.csv",
        "top15": folder / f"top10_acceleration_15d_{stamp}_{source.lower()}.csv",
        "potential": folder / f"top20_potential_{stamp}_{source.lower()}.csv",
        "review": folder / f"review_heat_preanalysis_{stamp}_{source.lower()}.csv",
        "diagnostics": folder / f"home_category_diagnostics_{stamp}_{source.lower()}.csv",
    }
    write_csv(files["all"], full)
    write_csv(files["top7"], [_display(row, index + 1, top7, top15, potential) for index, row in enumerate(top7_rows)])
    write_csv(files["top15"], [_display(row, index + 1, top7, top15, potential) for index, row in enumerate(top15_rows)])
    write_csv(files["potential"], [_display(row, index + 1, top7, top15, potential) for index, row in enumerate(potential_rows)])
    write_csv(files["review"], [_review_display(row, index + 1) for index, row in enumerate(review_rows)], REVIEW_HEADERS)
    write_csv(files["diagnostics"], diagnostics, DIAGNOSTIC_HEADERS)
    return {
        "files": {key: str(value) for key, value in files.items()}, "rows": len(full), "top7": len(top7_rows), "top15": len(top15_rows),
        "potential": len(potential_rows), "review_analyzed": len(review_rows), "categories_covered": sum(item["有效商品数"] > 0 for item in diagnostics),
        "category_diagnostics": diagnostics, "eligible7": eligible7, "eligible15": eligible15,
    }
