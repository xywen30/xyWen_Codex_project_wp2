from app.discovery.deduplicator import deduplicate
from app.models import SearchResult

def test_same_product_query_variants_deduplicate():
    base=dict(engine="google",keyword="полотенце",category="家纺",title="T",snippet="",collected_at="2026-08-17T00:00:00+08:00",data_source="REAL")
    rows=[SearchResult(rank=2,url="https://ozon.ru/product/a-123456789/?a=1",**base),SearchResult(rank=1,url="https://www.ozon.ru/product/a-123456789/?b=2",**base)]
    result=deduplicate(rows); assert len(result)==1 and result[0].rank==1
