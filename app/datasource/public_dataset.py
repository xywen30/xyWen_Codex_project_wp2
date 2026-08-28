from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import httpx

from app.category_config import classify_home_category
from app.discovery.deduplicator import deduplicate
from app.models import SearchResult, SourceDiagnostic


URLS = [
 "https://www.s-shot.ru/datasets/mi-series-ozon-home-q-home-bed-linen/",
 "https://www.s-shot.ru/datasets/mi-series-ozon-home-q-home-blanket/",
 "https://www.s-shot.ru/datasets/mi-series-ozon-home-q-home-towel/",
 "https://www.s-shot.ru/datasets/mi-series-ozon-household_chemicals-q-household-dishwashing/",
 "https://www.s-shot.ru/datasets/mi-series-ozon-household_chemicals-q-household-laundry-detergent/",
 "https://www.s-shot.ru/datasets/mi-series-ozon-household_chemicals-q-household-laundry-gel/",
]


def parse_preview(text: str) -> dict:
    marker=r'\"initialPreviewPage\":'; pos=text.find(marker)
    if pos<0: raise ValueError("PUBLIC_PREVIEW_NOT_FOUND")
    normalized=text[pos+len(marker):].replace(r'\"','"').replace(r"\\", "\\")
    value,_=json.JSONDecoder().raw_decode(normalized)
    return value


class PublicDatasetSource:
    name="s_shot_public_dataset"
    def __init__(self, root: Path, timeout: int=25, delay: float=1.0):
        self.root=root; self.timeout=timeout; self.delay=delay; self.last_status=[]; self.raw_rows=[]; self.category_stats={}

    def _fetch(self, url: str) -> tuple[int,str,int]:
        start=time.perf_counter()
        response=httpx.get(url,timeout=self.timeout,follow_redirects=True,headers={"User-Agent":"OzonTrendRadar/2.0 public-preview"})
        return response.status_code,response.text,int((time.perf_counter()-start)*1000)

    def diagnose(self) -> SourceDiagnostic:
        try:
            status,text,elapsed=self._fetch(URLS[0]); blocked="HTTP_403" if status==403 else ("HTTP_429" if status==429 else "")
            count=len(parse_preview(text).get("rows",[])) if status==200 and not blocked else 0
            return SourceDiagnostic(self.name,"AVAILABLE" if count else "BLOCKED",status,"text/html",elapsed,count,count,blocked,datetime.now().astimezone().isoformat(),URLS[0])
        except Exception as exc:
            return SourceDiagnostic(self.name,"BLOCKED",None,"",0,0,0,type(exc).__name__,datetime.now().astimezone().isoformat(),URLS[0])

    def discover_all(self) -> list[SearchResult]:
        output=[]; now=datetime.now().astimezone().isoformat(); self.last_status=[]; self.raw_rows=[]
        for index,url in enumerate(URLS):
            try:
                status,text,elapsed=self._fetch(url)
                if status in {403,429}: self.last_status.append((url,status,0,"BLOCKED")); break
                page=parse_preview(text); rows=page.get("rows",[])
                for row in rows:
                    product_url=str(row.get("source_url") or "")
                    if not product_url.startswith("http"): product_url="https://"+product_url.lstrip("/")
                    price=Decimal(str(row["current_price"]))/100 if row.get("current_price") is not None else None
                    original_raw=row.get("old_price") if row.get("old_price") is not None else row.get("original_price")
                    original=Decimal(str(original_raw))/100 if original_raw is not None else None
                    image=row.get("image_url") or row.get("image") or row.get("picture_url")
                    title=str(row.get("title") or "Ozon商品"); query=str(row.get("query_text") or "公开家居数据")
                    category=classify_home_category(title,query,categories=None)
                    output.append(SearchResult("s_shot",query,category["category_level_1"],int(row.get("rank") or 999),title,product_url,"公开列表快照；不含真实销量",now,"REAL",price_rub=float(price) if price is not None else None,original_price_rub=float(original) if original is not None else None,image_url=image,rating=float(row["rating"]) if row.get("rating") is not None else None,review_count=int(row["review_count"]) if row.get("review_count") is not None else None,brand=row.get("brand_name"),seller=row.get("seller_name"),source_url=url,raw_snippet=json.dumps(row,ensure_ascii=False)))
                self.last_status.append((url,status,len(rows),"SUCCESS"))
            except Exception as exc: self.last_status.append((url,None,0,type(exc).__name__))
            if index<len(URLS)-1: time.sleep(self.delay)
        self.raw_rows=list(output)
        deduplicated=deduplicate(output)
        self.category_stats={
            "raw":dict(Counter(row.category for row in output)),
            "deduplicated":dict(Counter(row.category for row in deduplicated)),
        }
        return deduplicated

    def discover(self, keyword: dict) -> list[SearchResult]: return self.discover_all()
