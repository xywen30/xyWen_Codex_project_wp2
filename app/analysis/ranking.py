from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import isnan
from typing import Iterable


def calculate_rank_velocity(points: list[tuple[date, float]]) -> float | None:
    clean=sorted({d:float(r) for d,r in points if r is not None}.items())
    if len(clean)<2: return None
    span=(clean[-1][0]-clean[0][0]).days
    return None if span<=0 else (clean[0][1]-clean[-1][1])/span


def calculate_rank_acceleration(previous: list[tuple[date,float]], recent: list[tuple[date,float]]) -> float | None:
    old=calculate_rank_velocity(previous); new=calculate_rank_velocity(recent)
    return None if old is None or new is None else new-old


def normalize_metric(values: Iterable[float | None], higher_better: bool=True) -> list[float]:
    items=list(values); valid=sorted(v for v in items if v is not None and not isnan(float(v)))
    if not valid: return [0.0]*len(items)
    if len(set(valid))==1: return [50.0 if v is not None else 0.0 for v in items]
    result=[]
    for value in items:
        if value is None: result.append(0.0); continue
        less=sum(v<float(value) for v in valid); equal=sum(v==float(value) for v in valid)
        pct=(less+(equal-1)/2)/(len(valid)-1)*100
        result.append(round(pct if higher_better else 100-pct,2))
    return result


def _recommend(trend: float, breakout: float, confidence: float) -> str:
    if trend>=90 and breakout>=85 and confidence>=70: return "S"
    if trend>=80 and breakout>=70 and confidence>=60: return "A"
    if trend>=65 and confidence>=45: return "B"
    return "C"


def analyze_products(snapshots: list[dict], products: list[dict], weights: dict[str,float], rate: dict) -> tuple[list[dict],dict]:
    if not snapshots: return [],{"history_days":0,"metric_date":date.today().isoformat()}
    by_product=defaultdict(list)
    for row in snapshots: by_product[str(row["product_id"])].append(row)
    metric_date=max(date.fromisoformat(str(r["snapshot_date"])[:10]) for r in snapshots)
    global_days=sorted({date.fromisoformat(str(r["snapshot_date"])[:10]) for r in snapshots})
    overall_span=(max(global_days)-min(global_days)).days+1 if global_days else 0
    product_map={str(p["product_id"]):p for p in products}; raw=[]
    for pid,rows in by_product.items():
        rows=sorted(rows,key=lambda r:(str(r["snapshot_date"]),int(r.get("rank") or 999)))
        by_day=defaultdict(list)
        for r in rows: by_day[date.fromisoformat(str(r["snapshot_date"])[:10])].append(r)
        points=sorted((d,min(float(x.get("rank") or 999) for x in rs)) for d,rs in by_day.items())
        recent=[p for p in points if metric_date-timedelta(days=6)<=p[0]<=metric_date]
        previous=[p for p in points if metric_date-timedelta(days=13)<=p[0]<=metric_date-timedelta(days=7)]
        all15=[p for p in points if metric_date-timedelta(days=14)<=p[0]<=metric_date]
        current_rows=by_day[max(by_day)]; current_rank=min(float(r.get("rank") or 999) for r in current_rows)
        current_keywords=len({r.get("keyword") for r in current_rows if r.get("keyword")})
        first_rows=by_day[min(by_day)]; first_coverage=len({r.get("keyword") for r in first_rows if r.get("keyword")})
        coverage_growth=current_keywords-first_coverage if len(by_day)>1 else None
        relevant_global=[d for d in global_days if metric_date-timedelta(days=14)<=d<=metric_date]
        presence=len({d for d in by_day if d in relevant_global})/max(1,len(relevant_global))
        engines=len({r.get("engine") for r in current_rows if r.get("engine")})
        rank_quality=max(0.0,min(100.0,101-current_rank))
        price_row=next((r for r in reversed(rows) if r.get("price_rub") is not None),{})
        engine_ranks={str(r.get("engine")):int(r.get("rank") or 999) for r in current_rows}
        velocity=calculate_rank_velocity(recent); prev_velocity=calculate_rank_velocity(previous)
        acceleration=calculate_rank_acceleration(previous,recent)
        earliest_rank=all15[0][1] if all15 else current_rank
        rank_change15=earliest_rank-current_rank if len(all15)>1 else None
        visibility_base=0.4*rank_quality+0.2*presence*100+0.15*min(100,engines/3*100)
        raw.append({
            "product_id":pid,"history_days":(max(by_day)-min(by_day)).days+1,"current_rank":current_rank,
            "rank_change_7d":recent[0][1]-recent[-1][1] if len(recent)>1 else None,"rank_change_15d":rank_change15,
            "rank_velocity_7d":velocity,"rank_velocity_prev7":prev_velocity,"rank_acceleration":acceleration,
            "keyword_coverage":current_keywords,"keyword_coverage_growth":coverage_growth,"presence_rate":round(presence,4),
            "engine_agreement_score":round(min(100,engines/3*100),2),"rank_quality":rank_quality,"visibility_base":visibility_base,
            "price_rub":price_row.get("price_rub"),"original_price_rub":price_row.get("original_price_rub"),"image_url":price_row.get("image_url"),
            "rating":price_row.get("rating"),"review_count":price_row.get("review_count"),
            "google_rank":engine_ranks.get("google"),"yandex_rank":engine_ranks.get("yandex"),"bing_rank":engine_ranks.get("bing"),
            "search_sources":"、".join(sorted({str(r.get('engine')) for r in current_rows if r.get('engine')})),
            "search_keywords":"、".join(sorted({str(r.get('keyword')) for r in current_rows if r.get('keyword')})),
            "collected_at":max(str(r.get("collected_at") or "") for r in current_rows),"source_url":price_row.get("source_url"),
            "monitored_days":(metric_date-date.fromisoformat(product_map.get(pid,{}).get("first_seen_at",rows[0]["collected_at"])[:10])).days+1,
        })
    velocity_norm=normalize_metric([r["rank_velocity_7d"] for r in raw]); acceleration_norm=normalize_metric([r["rank_acceleration"] for r in raw]); coverage_norm=normalize_metric([r["keyword_coverage"] for r in raw]); coverage_growth_norm=normalize_metric([r["keyword_coverage_growth"] for r in raw]); visibility_base_norm=normalize_metric([r["visibility_base"] for r in raw]); visibility_growth_norm=normalize_metric([(r["rank_change_15d"] if r["rank_change_15d"] is not None else None) for r in raw])
    for i,row in enumerate(raw):
        visibility=0.4*row["rank_quality"]+0.25*coverage_norm[i]+0.2*row["presence_rate"]*100+0.15*row["engine_agreement_score"]
        row["visibility_score"]=round(max(0,min(100,visibility)),2)
        row["visibility_growth"]=visibility_growth_norm[i] if row["rank_change_15d"] is not None else None
        trend=(weights["rank_velocity"]*velocity_norm[i]+weights["rank_acceleration"]*acceleration_norm[i]+weights["keyword_coverage_growth"]*coverage_growth_norm[i]+weights["presence_rate"]*row["presence_rate"]*100+weights["engine_agreement"]*row["engine_agreement_score"]+weights["search_visibility"]*row["visibility_score"])
        breakout=0.35*velocity_norm[i]+0.30*acceleration_norm[i]+0.20*coverage_growth_norm[i]+0.15*visibility_growth_norm[i]
        recency=max(0,100-min(100,row["monitored_days"]*4)); potential=0.30*recency+0.35*breakout+0.20*coverage_growth_norm[i]+0.15*visibility_growth_norm[i]
        confidence=min(100,0.35*row["engine_agreement_score"]+0.25*coverage_norm[i]+0.40*row["presence_rate"]*100)
        row.update(trend_score=round(trend,2),breakout_score=round(breakout,2),potential_score=round(potential,2),confidence_score=round(confidence,2),confidence_level="高" if confidence>=70 else ("中" if confidence>=45 else "低"))
        row["recommendation_level"]=_recommend(row["trend_score"],row["breakout_score"],row["confidence_score"])
        reasons=[]
        if row["rank_velocity_7d"] is not None and row["rank_velocity_7d"]>0: reasons.append(f"排名平均每天提升{row['rank_velocity_7d']:.1f}名")
        if row["keyword_coverage_growth"] is not None and row["keyword_coverage_growth"]>0: reasons.append(f"关键词覆盖增加{row['keyword_coverage_growth']}个")
        if row["engine_agreement_score"]>=66: reasons.append("多个搜索来源共同发现")
        if not reasons: reasons.append("当前公开排名、覆盖与出现频率形成早期信号")
        row["recommendation_reason"]="；".join(reasons)+"；建议进一步调研，不代表销量或盈利保证"
        row["price_cny"]=round(row["price_rub"]*rate["rub_cny"],2) if row["price_rub"] is not None else None
        row["original_price_cny"]=round(row["original_price_rub"]*rate["rub_cny"],2) if row["original_price_rub"] is not None else None
        row["discount_rate"]=round((1-row["price_rub"]/row["original_price_rub"])*100,2) if row["price_rub"] is not None and row["original_price_rub"] else None
        row.update(rub_cny=rate["rub_cny"],exchange_rate_date=rate["date"],exchange_rate_source=rate["source"],sales=None,clicks=None,dwell_seconds=None)
        row.pop("rank_quality",None); row.pop("visibility_base",None)
    return raw,{"history_days":overall_span,"metric_date":metric_date.isoformat(),"distinct_snapshot_days":len(global_days)}
