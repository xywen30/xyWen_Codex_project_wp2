from app.analysis.ranking import analyze_products
from tests.test_presence import W,R

def test_keyword_growth():
    s=[{"product_id":"1","snapshot_date":"2026-08-01","rank":50,"keyword":"a","engine":"google","collected_at":"2026-08-01T00:00:00"}]
    s += [{"product_id":"1","snapshot_date":"2026-08-07","rank":20+i,"keyword":k,"engine":"google","collected_at":"2026-08-07T00:00:00"} for i,k in enumerate(("a","b","c"))]
    p=[{"product_id":"1","first_seen_at":"2026-08-01T00:00:00","last_seen_at":"2026-08-07T00:00:00"}]
    rows,_=analyze_products(s,p,W,R); assert rows[0]["keyword_coverage"]==3 and rows[0]["keyword_coverage_growth"]==2
