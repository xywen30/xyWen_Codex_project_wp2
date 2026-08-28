from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.discovery.base import DataSource
from app.discovery.deduplicator import deduplicate
from app.models import SearchResult, SourceDiagnostic


ENGINE_URLS = {
    "google": "https://www.google.com/search?q={query}&num=10",
    "yandex": "https://yandex.com/search/?text={query}",
    "bing": "https://www.bing.com/search?q={query}&count=10",
}


class SearchEngineSource(DataSource):
    def __init__(self, name: str, root: Path, timeout: int = 20, cache_hours: int = 12):
        self.name = name.lower(); self.root = root; self.timeout = timeout; self.cache_hours = cache_hours
        self.cache = root / "data" / "cache" / self.name; self.cache.mkdir(parents=True, exist_ok=True)

    def _url(self, query: str) -> str:
        return ENGINE_URLS[self.name].format(query=quote_plus(query))

    def _get(self, query: str) -> tuple[int, str, str, int]:
        key = str(abs(hash(query)))
        cache_path = self.cache / f"{key}.json"
        if cache_path.exists() and datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime) < timedelta(hours=self.cache_hours):
            data=json.loads(cache_path.read_text(encoding="utf-8")); return data["status"],data["content_type"],data["text"],data["elapsed_ms"]
        started=time.perf_counter()
        with httpx.Client(timeout=self.timeout,follow_redirects=True,headers={"User-Agent":"Mozilla/5.0 OzonTrendRadar/2.0 public-research"}) as client:
            response=client.get(self._url(query))
        elapsed=int((time.perf_counter()-started)*1000)
        text=response.text[:1_500_000]
        cache_path.write_text(json.dumps({"status":response.status_code,"content_type":response.headers.get("content-type",""),"text":text,"elapsed_ms":elapsed},ensure_ascii=False),encoding="utf-8")
        return response.status_code,response.headers.get("content-type",""),text,elapsed

    @staticmethod
    def _blocked(status: int, text: str) -> str:
        low=text.lower()
        if status == 403: return "HTTP_403"
        if status == 429: return "HTTP_429"
        if "captcha" in low or "smartcaptcha" in low: return "CAPTCHA"
        if "antibot" in low or "challenge" in low: return "ANTIBOT_CHALLENGE"
        return ""

    def diagnose(self) -> SourceDiagnostic:
        tested=datetime.now(timezone.utc).isoformat(); url=self._url('site:ozon.ru/product "полотенце"')
        try:
            status,ctype,text,elapsed=self._get('site:ozon.ru/product "полотенце"')
            blocked=self._blocked(status,text); count=text.lower().count("ozon.ru/product")
            state="BLOCKED" if blocked else ("AVAILABLE" if count else "PARTIAL")
            return SourceDiagnostic(self.name,state,status,ctype,elapsed,count,count,blocked,tested,url)
        except Exception as exc:
            return SourceDiagnostic(self.name,"BLOCKED",None,"",0,0,0,type(exc).__name__,tested,url)

    def discover(self, keyword: dict) -> list[SearchResult]:
        query=f'site:ozon.ru/product "{keyword["keyword"]}"'
        status,_,text,_=self._get(query)
        if self._blocked(status,text): return []
        soup=BeautifulSoup(text,"lxml"); rows=[]; seen=set()
        for anchor in soup.select("a[href]"):
            href=anchor.get("href","")
            if "ozon.ru/product" not in href: continue
            if href.startswith("/url?q="): href=href.split("/url?q=",1)[1].split("&",1)[0]
            if href in seen: continue
            seen.add(href); title=anchor.get_text(" ",strip=True) or "Ozon商品"
            parent=anchor.parent.get_text(" ",strip=True) if anchor.parent else title
            rows.append(SearchResult(self.name,keyword["keyword"],keyword["category_cn"],len(rows)+1,title,href,parent,datetime.now().astimezone().isoformat(),"REAL",source_url=self._url(query),raw_snippet=parent))
            if len(rows)>=10: break
        return deduplicate(rows)
