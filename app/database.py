from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.models import SearchResult, SourceDiagnostic


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS products(
 product_id TEXT NOT NULL, data_source TEXT NOT NULL CHECK(data_source IN ('REAL','DEMO')),
 title TEXT NOT NULL, url TEXT NOT NULL, category TEXT, brand TEXT, seller TEXT,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, first_engine TEXT,
 canonical_url_hash TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(product_id,data_source)
);
CREATE TABLE IF NOT EXISTS search_snapshots(
 id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, engine TEXT NOT NULL,
 keyword TEXT NOT NULL, category TEXT, rank INTEGER, title TEXT, url TEXT, snippet TEXT,
 raw_snippet TEXT, collected_at TEXT NOT NULL, snapshot_date TEXT NOT NULL,
 data_source TEXT NOT NULL CHECK(data_source IN ('REAL','DEMO')),
 price_rub REAL, original_price_rub REAL, image_url TEXT, rating REAL, review_count INTEGER, source_url TEXT,
 sales INTEGER NULL, clicks INTEGER NULL, dwell_seconds REAL NULL,
 UNIQUE(product_id,snapshot_date,engine,keyword,data_source)
);
CREATE INDEX IF NOT EXISTS ix_snapshot_product_date ON search_snapshots(product_id,snapshot_date,data_source);
CREATE INDEX IF NOT EXISTS ix_snapshot_engine_keyword ON search_snapshots(engine,keyword,snapshot_date,data_source);
CREATE TABLE IF NOT EXISTS product_metrics(
 product_id TEXT NOT NULL, metric_date TEXT NOT NULL, data_source TEXT NOT NULL,
 history_days INTEGER, current_rank REAL, rank_change_7d REAL, rank_change_15d REAL,
 rank_velocity_7d REAL, rank_velocity_prev7 REAL, rank_acceleration REAL,
 keyword_coverage INTEGER, keyword_coverage_growth REAL, presence_rate REAL,
 engine_agreement_score REAL, visibility_score REAL, visibility_growth REAL,
 trend_score REAL, breakout_score REAL, potential_score REAL, confidence_score REAL,
 confidence_level TEXT, recommendation_level TEXT, recommendation_reason TEXT,
 price_rub REAL, original_price_rub REAL, discount_rate REAL, price_cny REAL, original_price_cny REAL,
 rub_cny REAL, exchange_rate_date TEXT, exchange_rate_source TEXT,
 sales INTEGER NULL, clicks INTEGER NULL, dwell_seconds REAL NULL,
 PRIMARY KEY(product_id,metric_date,data_source)
);
CREATE TABLE IF NOT EXISTS source_status(
 source TEXT PRIMARY KEY, status TEXT, http_status INTEGER, content_type TEXT,
 elapsed_ms INTEGER, result_count INTEGER, ozon_url_count INTEGER,
 blocked_reason TEXT, tested_at TEXT, request_url TEXT
);
CREATE TABLE IF NOT EXISTS runs(
 run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, data_source TEXT,
 keyword_count INTEGER, request_count INTEGER, success_count INTEGER, failure_count INTEGER,
 result_count INTEGER, product_count INTEGER, new_products INTEGER, snapshot_count INTEGER,
 status TEXT, report_path TEXT, error_summary TEXT
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def initialize(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)

    def upsert_results(self, rows: Iterable[SearchResult]) -> tuple[int, int, int]:
        new_products = snapshots = total = 0
        now = datetime.now().isoformat()
        with self.connect() as con:
            for row in rows:
                total += 1
                exists = con.execute("SELECT 1 FROM products WHERE product_id=? AND data_source=?", (row.product_id, row.data_source)).fetchone()
                new_products += int(exists is None)
                con.execute("""INSERT INTO products(product_id,data_source,title,url,category,brand,seller,first_seen_at,last_seen_at,first_engine,canonical_url_hash,created_at,updated_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id,data_source) DO UPDATE SET
                 title=excluded.title,url=excluded.url,category=COALESCE(excluded.category,products.category),brand=COALESCE(excluded.brand,products.brand),
                 seller=COALESCE(excluded.seller,products.seller),last_seen_at=excluded.last_seen_at,updated_at=excluded.updated_at""",
                 (row.product_id,row.data_source,row.title,row.canonical_url or row.url,row.category,row.brand,row.seller,row.collected_at,row.collected_at,row.engine,row.product_id,now,now))
                cur = con.execute("""INSERT INTO search_snapshots(product_id,engine,keyword,category,rank,title,url,snippet,raw_snippet,collected_at,snapshot_date,data_source,price_rub,original_price_rub,image_url,rating,review_count,source_url,sales,clicks,dwell_seconds)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL) ON CONFLICT(product_id,snapshot_date,engine,keyword,data_source) DO UPDATE SET
                 rank=excluded.rank,title=excluded.title,url=excluded.url,snippet=excluded.snippet,raw_snippet=excluded.raw_snippet,collected_at=excluded.collected_at,
                 price_rub=COALESCE(excluded.price_rub,search_snapshots.price_rub),original_price_rub=COALESCE(excluded.original_price_rub,search_snapshots.original_price_rub),
                 image_url=COALESCE(excluded.image_url,search_snapshots.image_url),rating=COALESCE(excluded.rating,search_snapshots.rating),review_count=COALESCE(excluded.review_count,search_snapshots.review_count),source_url=excluded.source_url""",
                 (row.product_id,row.engine,row.keyword,row.category,row.rank,row.title,row.canonical_url or row.url,row.snippet,row.raw_snippet or row.snippet,row.collected_at,row.collected_at[:10],row.data_source,row.price_rub,row.original_price_rub,row.image_url,row.rating,row.review_count,row.source_url))
                snapshots += int(cur.rowcount > 0)
        return new_products, snapshots, total

    def save_diagnostic(self, row: SourceDiagnostic) -> None:
        with self.connect() as con:
            con.execute("""INSERT INTO source_status(source,status,http_status,content_type,elapsed_ms,result_count,ozon_url_count,blocked_reason,tested_at,request_url)
             VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET status=excluded.status,http_status=excluded.http_status,
             content_type=excluded.content_type,elapsed_ms=excluded.elapsed_ms,result_count=excluded.result_count,ozon_url_count=excluded.ozon_url_count,
             blocked_reason=excluded.blocked_reason,tested_at=excluded.tested_at,request_url=excluded.request_url""",
             (row.source,row.status,row.http_status,row.content_type,row.elapsed_ms,row.result_count,row.ozon_url_count,row.blocked_reason,row.tested_at,row.request_url))

    def snapshots(self, source: str) -> list[dict]:
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT s.*,p.brand,p.seller,p.first_seen_at,p.last_seen_at FROM search_snapshots s JOIN products p USING(product_id,data_source) WHERE s.data_source=? ORDER BY snapshot_date,product_id", (source,))]

    def products(self, source: str) -> list[dict]:
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM products WHERE data_source=?", (source,))]

    def save_metrics(self, rows: list[dict], source: str, metric_date: str) -> None:
        keys = ["product_id","metric_date","data_source","history_days","current_rank","rank_change_7d","rank_change_15d","rank_velocity_7d","rank_velocity_prev7","rank_acceleration","keyword_coverage","keyword_coverage_growth","presence_rate","engine_agreement_score","visibility_score","visibility_growth","trend_score","breakout_score","potential_score","confidence_score","confidence_level","recommendation_level","recommendation_reason","price_rub","original_price_rub","discount_rate","price_cny","original_price_cny","rub_cny","exchange_rate_date","exchange_rate_source","sales","clicks","dwell_seconds"]
        with self.connect() as con:
            for row in rows:
                payload = {k: row.get(k) for k in keys}; payload.update(metric_date=metric_date,data_source=source)
                columns=",".join(keys); marks=",".join(f":{k}" for k in keys)
                updates=",".join(f"{k}=excluded.{k}" for k in keys[3:])
                con.execute(f"INSERT INTO product_metrics({columns}) VALUES({marks}) ON CONFLICT(product_id,metric_date,data_source) DO UPDATE SET {updates}", payload)

    def latest_metrics(self, source: str) -> list[dict]:
        with self.connect() as con:
            return [dict(r) for r in con.execute("""SELECT m.*,p.title,p.url,p.category,p.first_seen_at,p.last_seen_at,p.brand,p.seller
             FROM product_metrics m JOIN products p USING(product_id,data_source)
             WHERE m.data_source=? AND m.metric_date=(SELECT MAX(metric_date) FROM product_metrics WHERE data_source=?)
             ORDER BY m.trend_score DESC""", (source,source))]

    def source_statuses(self) -> list[dict]:
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM source_status ORDER BY source")]

    def backup(self, keep: int = 7) -> Path | None:
        if not self.path.exists(): return None
        folder = self.path.parent / "backups"; folder.mkdir(exist_ok=True)
        target = folder / f"ozon_trend_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(self.path, target)
        for old in sorted(folder.glob("ozon_trend_*.db"), key=lambda p:p.stat().st_mtime, reverse=True)[keep:]: old.unlink(missing_ok=True)
        return target
