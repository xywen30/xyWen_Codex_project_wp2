from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analysis.review_heat import build_review_heat_map
from app.category_config import classify_home_category
from app.config import settings
from app.services.product_search import filter_products
from app.services.translation_service import fallback_title_cn


st.set_page_config(page_title="Ozon 家居爆品趋势雷达", page_icon="📡", layout="wide")


@st.cache_data(ttl=60)
def query(sql: str, params=()) -> pd.DataFrame:
    if not settings.database_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(settings.database_path) as connection:
        return pd.read_sql_query(sql, connection, params=params)


source = "REAL"
st.sidebar.success("当前仅展示 REAL 真实公开数据")
page = st.sidebar.selectbox(
    "页面",
    ["首页", "7天爆品榜", "15天加速榜", "潜力商品TOP20", "评论热度分析", "商品检索", "商品趋势详情", "关键词分析", "类目趋势", "数据源状态", "运行日志", "系统状态"],
)
st.title("📡 Ozon 家居爆品趋势雷达")
st.caption("搜索趋势雷达，不是销量报表。评论数变化与搜索曝光属于估算信号，不等于真实成交量。")
st.success("当前为 REAL：公开来源真实观察数据。趋势、评论热度与人民币价格属于 ESTIMATED（估算结果）。")

metrics = query(
    """SELECT m.*,p.title,p.url,p.category,p.brand,p.seller,p.first_seen_at,p.last_seen_at
    FROM product_metrics m JOIN products p USING(product_id,data_source)
    WHERE m.data_source=? AND m.metric_date=(SELECT MAX(metric_date) FROM product_metrics WHERE data_source=?)""",
    (source, source),
)
products = query("SELECT * FROM products WHERE data_source=?", (source,))
snapshots = query("SELECT * FROM search_snapshots WHERE data_source=?", (source,))
history_days = 0
if not snapshots.empty:
    history_days = (pd.to_datetime(snapshots.snapshot_date).max() - pd.to_datetime(snapshots.snapshot_date).min()).days + 1

if not metrics.empty:
    metrics["title_cn"] = [fallback_title_cn(str(row.title), "") for row in metrics.itertuples()]
    categories = [classify_home_category(row.title, "", row.category) for row in metrics.itertuples()]
    metrics["category_level_1"] = [item["category_level_1"] for item in categories]
    metrics["category_level_2"] = [item["category_level_2"] for item in categories]
    if not snapshots.empty:
        keyword_map = snapshots.groupby(snapshots.product_id.astype(str))["keyword"].apply(lambda values: "、".join(sorted(set(map(str, values))))).to_dict()
        metrics["search_keywords"] = metrics.product_id.astype(str).map(keyword_map).fillna("")
        metric_date = str(metrics.metric_date.max())
        heat_map = build_review_heat_map(snapshots.to_dict("records"), metric_date, set(metrics.product_id.astype(str)))
        for field in ("review_status", "reviews_7d", "reviews_15d", "reviews_30d", "review_activity", "review_heat_score", "review_heat_level", "review_reason", "review_risk"):
            metrics[field] = metrics.product_id.astype(str).map(lambda product_id: heat_map.get(product_id, {}).get(field))


def readable(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    rename = {
        "product_id": "商品ID/SKU", "title": "商品名称", "title_cn": "商品名称_中文名称", "url": "Ozon商品链接",
        "category_level_1": "一级类目", "category_level_2": "二级类目", "trend_score": "爆品趋势指数（估算）",
        "breakout_score": "爆发指数（估算）", "potential_score": "综合潜力指数（估算）", "confidence_score": "可信度分",
        "confidence_level": "可信度", "rank_change_7d": "7天排名变化", "rank_change_15d": "15天排名变化",
        "rank_velocity_7d": "最近排名速度", "rank_velocity_prev7": "前期排名速度", "rank_acceleration": "排名加速度",
        "keyword_coverage": "关键词覆盖数", "keyword_coverage_growth": "关键词覆盖增长", "visibility_score": "搜索曝光代理指数（估算）",
        "presence_rate": "出现频率", "engine_agreement_score": "多来源一致性", "price_rub": "当前价格（卢布）",
        "original_price_rub": "原价（卢布）", "discount_rate": "折扣率（%）", "price_cny": "当前价格（人民币估算）",
        "original_price_cny": "原价（人民币估算）", "rub_cny": "RUB/CNY换算率", "exchange_rate_date": "汇率日期",
        "rating": "评分", "review_count": "评论数", "reviews_7d": "7天评论增量（公开快照）",
        "reviews_15d": "15天评论增量（公开快照）", "reviews_30d": "30天评论增量（公开快照）",
        "review_heat_score": "评论热度评分（估算）", "review_heat_level": "热门预判", "review_reason": "热门原因",
        "review_risk": "风险提示", "recommendation_level": "关注等级", "recommendation_reason": "规则化理由",
        "first_seen_at": "首次发现", "last_seen_at": "最近发现", "search_keywords": "搜索关键词",
    }
    columns = [column for column in rename if column in frame.columns]
    return frame[columns].rename(columns=rename)


if page == "首页":
    today = str(pd.Timestamp.now().date())
    today_found = 0 if snapshots.empty else snapshots.loc[snapshots.snapshot_date == today, "product_id"].nunique()
    first_seen = 0 if products.empty else (pd.to_datetime(products.first_seen_at, format="mixed", errors="coerce").dt.date == pd.Timestamp.now().date()).sum()
    high = 0 if metrics.empty else (metrics.potential_score >= 70).sum()
    available = query("SELECT COUNT(*) n FROM source_status WHERE status='AVAILABLE'").iloc[0, 0] if settings.database_path.exists() else 0
    columns = st.columns(4)
    for column, label, value in zip(columns, ["今日发现商品", "累计监控商品", "关键词数量", "可用数据源"], [today_found, len(products), len(settings.keywords()), available]):
        column.metric(label, value)
    columns = st.columns(4)
    for column, label, value in zip(columns, ["今日新增商品", "高潜商品", "历史跨度", "当前模式"], [first_seen, high, f"{history_days}天", source]):
        column.metric(label, value)
    if history_days < 7:
        st.info("真实历史不足7天，7天榜仍在积累；当前结果仅作早期趋势参考。")
    st.subheader("搜索曝光代理榜")
    st.dataframe(readable(metrics.sort_values("visibility_score", ascending=False).head(10)), use_container_width=True, hide_index=True)
elif page == "7天爆品榜":
    if history_days < 7 or metrics.rank_velocity_7d.notna().sum() < 10:
        st.warning("数据积累中：真实连续快照不足，暂不生成正式7天榜。")
    else:
        st.dataframe(readable(metrics.sort_values(["trend_score", "visibility_score"], ascending=False).head(10)), use_container_width=True, hide_index=True)
elif page == "15天加速榜":
    if history_days < 15 or metrics.rank_acceleration.notna().sum() < 10:
        st.warning("数据积累中：15天连续历史不足，暂不生成正式加速榜。")
    else:
        st.dataframe(readable(metrics.sort_values(["breakout_score", "trend_score"], ascending=False).head(10)), use_container_width=True, hide_index=True)
elif page == "潜力商品TOP20":
    st.dataframe(readable(metrics.sort_values(["potential_score", "confidence_score"], ascending=False).head(20)), use_container_width=True, hide_index=True)
elif page == "评论热度分析":
    st.info("评论热度只使用公开评论总数快照变化、评分与时间衰减；不等于销量，且公开源没有单条评论日期。")
    analyzed = metrics[metrics.review_status.isin(["available", "partial"])].sort_values(["review_heat_score", "potential_score"], ascending=False)
    st.dataframe(readable(analyzed), use_container_width=True, hide_index=True)
elif page == "商品检索":
    st.subheader("商品搜索与筛选")
    row1 = st.columns(3)
    keyword = row1[0].text_input("关键词（俄文/中文/商品ID）")
    category_options = sorted(metrics.category_level_1.dropna().unique().tolist()) if not metrics.empty else []
    selected_categories = row1[1].multiselect("一级类目", category_options)
    review_min = row1[2].number_input("最低评论数", min_value=0, value=0, step=100)
    row2 = st.columns(4)
    heat_min = row2[0].slider("最低评论热度", 0, 100, 0)
    potential_min = row2[1].slider("最低潜力指数", 0, 100, 0)
    price_min = row2[2].number_input("最低价格 RUB", min_value=0.0, value=0.0)
    price_max_value = float(pd.to_numeric(metrics.price_rub, errors="coerce").max()) if not metrics.empty and metrics.price_rub.notna().any() else 0.0
    price_max = row2[3].number_input("最高价格 RUB（0为不限）", min_value=0.0, value=0.0)
    filtered = filter_products(metrics, keyword, selected_categories, heat_min, potential_min, price_min, price_max or None, review_min)
    st.caption(f"找到 {len(filtered)} 个商品；当前样本最高公开价格约 {price_max_value:,.0f} RUB。")
    st.dataframe(readable(filtered.sort_values(["potential_score", "review_heat_score"], ascending=False)), use_container_width=True, hide_index=True)
elif page == "商品趋势详情":
    if products.empty:
        st.info("暂无数据")
    else:
        labels = {f"{row.title}｜{row.product_id}": row.product_id for row in products.itertuples()}
        product_id = labels[st.selectbox("选择商品", list(labels))]
        st.dataframe(readable(metrics[metrics.product_id.astype(str) == str(product_id)]), use_container_width=True, hide_index=True)
        time_series = query("SELECT snapshot_date,engine,MIN(rank) rank,COUNT(DISTINCT keyword) keyword_coverage FROM search_snapshots WHERE data_source=? AND product_id=? GROUP BY snapshot_date,engine ORDER BY snapshot_date", (source, str(product_id)))
        if not time_series.empty:
            figure = px.line(time_series, x="snapshot_date", y="rank", color="engine", markers=True, title="搜索来源排名变化（排名1最好）")
            figure.update_yaxes(autorange="reversed")
            st.plotly_chart(figure, use_container_width=True)
elif page == "关键词分析":
    st.dataframe(query("SELECT keyword AS 关键词,COUNT(DISTINCT product_id) AS 发现商品数 FROM search_snapshots WHERE data_source=? GROUP BY keyword ORDER BY 发现商品数 DESC", (source,)), use_container_width=True, hide_index=True)
elif page == "类目趋势":
    st.dataframe(metrics.groupby("category_level_1", as_index=False).agg(商品数=("product_id", "nunique"), 平均趋势指数=("trend_score", "mean"), 平均评论热度=("review_heat_score", "mean")).rename(columns={"category_level_1": "一级类目"}), use_container_width=True, hide_index=True)
elif page == "数据源状态":
    st.dataframe(query("SELECT source AS 数据源,status AS 状态,http_status AS HTTP状态,elapsed_ms AS 耗时毫秒,result_count AS 结果数,blocked_reason AS 阻塞原因,tested_at AS 测试时间 FROM source_status"), use_container_width=True, hide_index=True)
elif page == "运行日志":
    st.dataframe(query("SELECT started_at AS 开始时间,finished_at AS 结束时间,data_source AS 数据模式,product_count AS 商品数,snapshot_count AS 快照数,status AS 状态,report_path AS 报告路径,error_summary AS 错误摘要 FROM runs ORDER BY started_at DESC LIMIT 50"), use_container_width=True, hide_index=True)
elif page == "系统状态":
    st.write({"项目目录": str(ROOT), "数据库": str(settings.database_path), "REAL商品": len(products), "历史跨度": history_days, "真实销量": "无可靠公开数据", "评论热度": "公开快照增量代理", "演示数据": "不在界面展示"})
