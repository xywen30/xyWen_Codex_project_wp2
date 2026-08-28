from __future__ import annotations

import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config import settings
from app.database import Database
from app.datasource.ozon_direct import OzonDirectSource
from app.datasource.public_dataset import PublicDatasetSource
from app.datasource.search_source import SearchEngineSource
from app.utils.logger import get_logger


def main() -> dict:
    settings.ensure(); db=Database(settings.database_path); db.initialize(); log=get_logger(ROOT,"discovery")
    sources=[SearchEngineSource("yandex",ROOT),SearchEngineSource("google",ROOT),SearchEngineSource("bing",ROOT),OzonDirectSource(False),PublicDatasetSource(ROOT)]
    rows=[]
    for source in sources:
        row=source.diagnose(); db.save_diagnostic(row); rows.append(row)
        log.info("%s | DIAGNOSE | status=%s http=%s ozon_urls=%s reason=%s",row.source,row.status,row.http_status,row.ozon_url_count,row.blocked_reason)
    lines=["# 数据源诊断报告","","> 单次、低频、无验证码绕过。Ozon Direct使用既有403证据保持熔断，不重复请求。","","|来源|状态|HTTP|响应类型|耗时ms|结果数|Ozon URL|阻塞原因|","|---|---:|---:|---|---:|---:|---:|---|"]
    for r in rows: lines.append(f"|{r.source}|{r.status}|{r.http_status or ''}|{r.content_type}|{r.elapsed_ms}|{r.result_count}|{r.ozon_url_count}|{r.blocked_reason or ''}|")
    (ROOT/"reports"/"source_diagnostic.md").write_text("\n".join(lines),encoding="utf-8")
    (ROOT/"reports"/"data_source_report.md").write_text("\n".join(lines+["","S-SHOT公开数据集用于REAL商品发现与列表信号；不含真实销量、点击或停留时间。"]),encoding="utf-8")
    return {r.source:r.status for r in rows}


if __name__=="__main__": print(main())
