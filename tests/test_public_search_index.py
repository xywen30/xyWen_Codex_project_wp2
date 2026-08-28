from pathlib import Path

from app.datasource.public_search_index import PublicSearchIndexSnapshotSource


def test_public_search_index_snapshot_is_real_auditable_and_diverse():
    project_root = Path(__file__).resolve().parents[1]
    source = PublicSearchIndexSnapshotSource(project_root)
    rows = source.discover_all()
    assert source.last_status == "SUCCESS"
    assert len(rows) >= 15
    assert len({row.category for row in rows}) >= 6
    assert all(row.data_source == "REAL" for row in rows)
    assert all(row.engine == "public_web_index" for row in rows)
    assert all(row.product_id and row.url.startswith("https://www.ozon.ru/product/") for row in rows)
    assert all("可能滞后" in (row.raw_snippet or "") for row in rows)
