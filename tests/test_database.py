from app.database import Database
from app.discovery.deduplicator import deduplicate
from app.models import SearchResult

def row(source): return SearchResult("google","k","c",1,"t","https://www.ozon.ru/product/a-123456789/","s","2026-08-17T00:00:00+08:00",source)
def test_database_real_demo_isolation(tmp_path):
    db=Database(tmp_path/"x.db"); db.initialize(); db.upsert_results(deduplicate([row("REAL"),row("DEMO")]))
    assert len(db.products("REAL"))==1 and len(db.products("DEMO"))==1
    assert db.snapshots("REAL")[0]["sales"] is None
