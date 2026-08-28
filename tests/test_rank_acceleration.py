from datetime import date
from app.analysis.ranking import calculate_rank_acceleration

def test_acceleration():
    old=[(date(2026,8,1),80),(date(2026,8,7),68)]
    new=[(date(2026,8,8),68),(date(2026,8,14),20)]
    assert calculate_rank_acceleration(old,new)==6
