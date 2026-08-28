from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from app.category_config import balanced_search_keywords, classify_home_category, load_home_categories
from app.database import Database
from app.datasource.public_dataset import PublicDatasetSource
from app.datasource.public_search_index import PublicSearchIndexSnapshotSource
from app.datasource.search_source import SearchEngineSource
from app.discovery.deduplicator import deduplicate
from app.models import SearchResult
from app.utils.logger import get_logger


class DiscoveryService:
    def __init__(self, root: Path, db: Database): self.root=root; self.db=db; self.log=get_logger(root,"discovery")

    def import_legacy_google(self) -> list[SearchResult]:
        path=Path(r"W:\Ozon\ozon-analyzer\data\ozon_history.db")
        if not path.exists(): return []
        con=sqlite3.connect(path); con.row_factory=sqlite3.Row
        rows=con.execute("""SELECT s.*,p.product_name,p.product_url,p.category_level_1,p.brand,p.seller_name
         FROM product_snapshots s JOIN products p USING(product_id) WHERE s.source_type='google_search_index'""").fetchall(); con.close()
        output=[]
        for r in rows:
            title=r["product_name"] or "Ozon商品"; keyword=r["search_keyword"] or "legacy_google_index"
            category=classify_home_category(title,keyword,r["category_level_1"] or "创意家居/生活用品")
            output.append(SearchResult("google",keyword,category["category_level_1"],int(r["list_position"] or 999),title,r["product_url"],"历史合法Google公开索引缓存；未经Ozon详情页复核",r["collected_at"],"REAL",product_id=str(r["product_id"]),canonical_url=r["product_url"],price_rub=float(r["current_price"]) if r["current_price"] is not None else None,rating=float(r["rating"]) if r["rating"] is not None else None,review_count=r["review_count"],brand=r["brand"],seller=r["seller_name"],source_url=r["source_url"],raw_snippet="历史合法Google公开索引缓存"))
        return output

    def _category_diagnostics(self, raw_rows: list[SearchResult], rows: list[SearchResult], attempted: list[dict]) -> list[dict]:
        matrix=load_home_categories(self.root)
        raw_counts=Counter(row.category for row in raw_rows)
        dedup_counts=Counter(row.category for row in rows)
        attempted_terms=defaultdict(set)
        for item in attempted:
            attempted_terms[item["category_cn"]].add(item["keyword"])
        discovered_keywords=defaultdict(set); sources=defaultdict(set)
        for row in raw_rows:
            discovered_keywords[row.category].add(row.keyword)
            sources[row.category].add(row.engine)
        output=[]
        for category in matrix:
            name=category["category_cn"]
            output.append({
                "category":name,
                "configured_keywords":len(category.get("keywords_ru",[])),
                "attempted_keywords":len(attempted_terms[name] | discovered_keywords[name]),
                "raw_candidates":raw_counts[name],
                "deduplicated_products":dedup_counts[name],
                "valid_products":sum(1 for row in rows if row.category==name and row.product_id and str(row.canonical_url or row.url).startswith("http")),
                "source_count":len(sources[name]),
            })
        return output

    def run(self, keywords: list[dict], engine_status: dict[str,str] | None=None) -> dict:
        self.log.info("discovery | START | 开始REAL数据发现")
        public=PublicDatasetSource(self.root); rows=public.discover_all(); raw_rows=list(public.raw_rows); self.log.info("s_shot | RESULT | found=%s",len(rows))
        public_index=PublicSearchIndexSnapshotSource(self.root); index_rows=public_index.discover_all(); rows.extend(index_rows); raw_rows.extend(index_rows)
        self.log.info("public_web_index | RESULT | status=%s found=%s limitation=%s",public_index.last_status,len(index_rows),public_index.limitations)
        legacy=self.import_legacy_google(); rows.extend(legacy); raw_rows.extend(legacy); self.log.info("google_cache | RESULT | found=%s",len(legacy))
        requests=6; successes=sum(1 for _,status,_,result in public.last_status if status==200 and result=="SUCCESS"); failures=requests-successes
        statuses=engine_status or {}; attempted=[]
        for engine in ("yandex","google","bing"):
            if statuses.get(engine)!="AVAILABLE": continue
            source=SearchEngineSource(engine,self.root)
            for keyword in balanced_search_keywords(keywords,per_category=1,max_total=10):
                attempted.append(keyword)
                found=source.discover(keyword); rows.extend(found); raw_rows.extend(found); requests+=1; successes+=int(bool(found)); failures+=int(not found)
                self.log.info("%s | QUERY | keyword=%s found=%s",engine,keyword["keyword"],len(found))
        rows=deduplicate(rows)
        diagnostics=self._category_diagnostics(raw_rows,rows,attempted)
        for item in diagnostics:
            self.log.info("category | %s | keywords=%s raw=%s deduplicated=%s valid=%s sources=%s",item["category"],item["attempted_keywords"],item["raw_candidates"],item["deduplicated_products"],item["valid_products"],item["source_count"])
        new_products,snapshots,total=self.db.upsert_results(rows)
        self.log.info("database | INSERT | products=%s snapshots=%s",new_products,snapshots)
        return {"request_count":requests,"success_count":successes,"failure_count":failures,"result_count":total,"new_products":new_products,"snapshot_count":snapshots,"products":len({r.product_id for r in rows}),"public_status":public.last_status,"public_index_status":public_index.last_status,"public_index_products":len(index_rows),"category_diagnostics":diagnostics}
