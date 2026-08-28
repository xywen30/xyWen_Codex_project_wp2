from datetime import date
from app.analysis.ranking import calculate_rank_velocity

def test_rank_80_to_20(): assert calculate_rank_velocity([(date(2026,8,1),80),(date(2026,8,7),20)])==10
def test_rank_20_to_80(): assert calculate_rank_velocity([(date(2026,8,1),20),(date(2026,8,7),80)])==-10
def test_single_or_null(): assert calculate_rank_velocity([(date(2026,8,1),20)]) is None
