from app.analysis.ranking import normalize_metric

def test_extreme_values_do_not_exceed_100(): assert max(normalize_metric([-999,0,999999]))==100
