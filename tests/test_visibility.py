from app.analysis.ranking import normalize_metric

def test_normalization_and_null(): assert normalize_metric([1,2,100,None])==[0.0,50.0,100.0,0.0]
