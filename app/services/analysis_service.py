from __future__ import annotations

from pathlib import Path

from app.analysis.ranking import analyze_products
from app.analysis.review_heat import apply_review_heat
from app.category_config import classify_home_category
from app.config import Settings
from app.database import Database
from app.services.exchange_rate import get_rate
from app.services.export_service import export_rankings
from app.services.translation_service import translate_product_titles
from app.utils.logger import get_logger


class AnalysisService:
    def __init__(self, settings: Settings, db: Database): self.settings=settings; self.db=db; self.log=get_logger(settings.root,"analysis")
    def run(self, source: str="REAL", discovery_diagnostics: list[dict] | None=None) -> dict:
        rows=self.db.snapshots(source); products=self.db.products(source); rate=get_rate(self.settings.root)
        metrics,meta=analyze_products(rows,products,self.settings.weights(),rate)
        joined=[]; pmap={p["product_id"]:p for p in products}
        for row in metrics:
            row.update(pmap.get(row["product_id"],{})); row["metric_date"]=meta["metric_date"]; row["data_source"]=source
            category=classify_home_category(row.get("title"),row.get("search_keywords"),row.get("category"))
            row["category"]=category["category_level_1"]; row["category_level_1"]=category["category_level_1"]; row["category_level_2"]=category["category_level_2"]
            joined.append(row)
        joined,review_summary=apply_review_heat(joined,rows,meta["metric_date"])
        self.db.save_metrics(joined,source,meta["metric_date"])
        translation=translate_product_titles(self.settings.root,joined,source)
        export=export_rankings(self.settings.root,joined,meta,source,discovery_diagnostics or [])
        self.log.info("review_heat | COMPLETE | candidates=%s success=%s unavailable=%s",review_summary["candidate_count"],review_summary["success_count"],review_summary["unavailable_count"])
        self.log.info("analysis | COMPLETE | source=%s products=%s history_days=%s top7=%s top15=%s potential_top20=%s categories=%s title_cn=%s fallback=%s",source,len(joined),meta["history_days"],export["top7"],export["top15"],export["potential"],export["categories_covered"],translation["cached_or_remote"],translation["fallback"])
        return {"metrics":len(joined),"meta":meta,"exchange_rate":rate,"translation":translation,"review":review_summary,"export":export}
