from app.analysis.ranking import analyze_products

W={"rank_velocity":.3,"rank_acceleration":.2,"keyword_coverage_growth":.15,"presence_rate":.15,"engine_agreement":.1,"search_visibility":.1}
R={"rub_cny":.08,"date":"2026-08-15","source":"CBR"}
def test_presence_uses_available_snapshot_days():
    s=[]
    for day in ("2026-08-01","2026-08-03"):
        s.append({"product_id":"1","snapshot_date":day,"rank":10,"keyword":"k","engine":"google","price_rub":500,"rating":4.8,"review_count":10,"collected_at":day+"T00:00:00"})
    p=[{"product_id":"1","first_seen_at":"2026-08-01T00:00:00","last_seen_at":"2026-08-03T00:00:00"}]
    rows,_=analyze_products(s,p,W,R); assert rows[0]["presence_rate"]==1.0
