from datetime import date
from app.analysis.ranking import calculate_rank_acceleration

def test_breakout_acceleration_positive(): assert calculate_rank_acceleration([(date(2026,8,1),90),(date(2026,8,7),84)],[(date(2026,8,8),84),(date(2026,8,14),24)])==9
