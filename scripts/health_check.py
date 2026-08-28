from __future__ import annotations

import csv,json,sqlite3,sys,zipfile
from datetime import date,datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config import settings


def main():
    checks={"root":ROOT.exists(),"venv":(ROOT/".venv"/"Scripts"/"python.exe").exists(),"database":settings.database_path.exists(),"config":len(settings.keywords())>=30,"weights":abs(sum(settings.weights().values())-1)<1e-9}
    details={}
    if settings.database_path.exists():
        with sqlite3.connect(settings.database_path) as con:
            checks["sqlite_integrity"]=con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            details["real_products"]=con.execute("SELECT COUNT(*) FROM products WHERE data_source='REAL'").fetchone()[0]
            details["demo_products"]=con.execute("SELECT COUNT(*) FROM products WHERE data_source='DEMO'").fetchone()[0]
            details["real_snapshots"]=con.execute("SELECT COUNT(*) FROM search_snapshots WHERE data_source='REAL'").fetchone()[0]
            details["original_price_count"]=con.execute("SELECT COUNT(*) FROM search_snapshots WHERE data_source='REAL' AND original_price_rub IS NOT NULL").fetchone()[0]
            details["image_count"]=con.execute("SELECT COUNT(*) FROM search_snapshots WHERE data_source='REAL' AND image_url IS NOT NULL").fetchone()[0]
            details["real_sales_non_null"]=con.execute("SELECT COUNT(*) FROM search_snapshots WHERE data_source='REAL' AND sales IS NOT NULL").fetchone()[0]
            details["real_demo_id_overlap"]=con.execute("SELECT COUNT(*) FROM products r JOIN products d USING(product_id) WHERE r.data_source='REAL' AND d.data_source='DEMO'").fetchone()[0]
            details["invalid_real_urls"]=con.execute("SELECT COUNT(*) FROM products WHERE data_source='REAL' AND url NOT LIKE 'https://%ozon.ru/product/%'").fetchone()[0]
            rate=con.execute("SELECT rub_cny FROM product_metrics WHERE data_source='REAL' ORDER BY metric_date DESC LIMIT 1").fetchone()
            details["rub_cny"]=rate[0] if rate else None
    checks["real_data_present"]=details.get("real_products",0)>0
    checks["real_demo_isolated"]=details.get("real_demo_id_overlap",1)==0
    checks["unknown_sales_blank"]=details.get("real_sales_non_null",1)==0
    checks["real_urls_valid_format"]=details.get("invalid_real_urls",1)==0
    checks["exchange_rate_direction"]=details.get("rub_cny") is not None and 0.01<float(details["rub_cny"])<1
    csv_path=ROOT/"data"/"exports"/f"ozon_home_trend_analysis_{date.today():%Y%m%d}_real.csv"
    checks["real_csv_exists"]=csv_path.exists()
    checks["real_csv_utf8_bom"]=csv_path.exists() and csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    required={"数据性质","商品ID/SKU","Ozon商品链接","当前价格（卢布）","原价（卢布）","折扣率（%）","当前价格（人民币估算）","RUB/CNY换算率","搜索来源","搜索关键词","抓取时间","真实销量"}
    headers=[]
    if csv_path.exists():
        with csv_path.open("r",encoding="utf-8-sig",newline="") as file: headers=next(csv.reader(file),[])
    checks["readable_fields_complete"]=required.issubset(headers)
    potential_path=ROOT/"data"/"exports"/f"top20_potential_{date.today():%Y%m%d}_real.csv"
    review_path=ROOT/"data"/"exports"/f"review_heat_preanalysis_{date.today():%Y%m%d}_real.csv"
    diagnostic_path=ROOT/"data"/"exports"/f"home_category_diagnostics_{date.today():%Y%m%d}_real.csv"
    potential_rows=[]; diagnostic_rows=[]
    if potential_path.exists():
        with potential_path.open("r",encoding="utf-8-sig",newline="") as file: potential_rows=list(csv.DictReader(file))
    if diagnostic_path.exists():
        with diagnostic_path.open("r",encoding="utf-8-sig",newline="") as file: diagnostic_rows=list(csv.DictReader(file))
    details["potential_top20_rows"]=len(potential_rows)
    details["potential_unique_ids"]=len({row.get("商品ID/SKU") for row in potential_rows})
    details["categories_covered"]=sum(int(float(row.get("有效商品数") or 0))>0 for row in diagnostic_rows)
    checks["potential_top20_exists"]=potential_path.exists()
    checks["potential_top20_unique"]=len(potential_rows)==details["potential_unique_ids"] and len(potential_rows)==min(20,details.get("real_products",0))
    checks["review_analysis_exists"]=review_path.exists()
    checks["category_diagnostics_exists"]=diagnostic_path.exists() and len(diagnostic_rows)==10
    checks["multiple_home_categories_covered"]=details["categories_covered"]>=3
    xlsx_path=ROOT/"网爬结果"/f"家居_{date.today():%Y%m%d}.xlsx"
    checks["daily_xlsx_exists"]=xlsx_path.exists()
    checks["daily_xlsx_valid_signature"]=xlsx_path.exists() and xlsx_path.read_bytes()[:2]==b"PK"
    details["native_hyperlinks"]=0
    if checks["daily_xlsx_valid_signature"]:
        with zipfile.ZipFile(xlsx_path,"r") as archive:
            workbook_xml=archive.read("xl/workbook.xml").decode("utf-8",errors="replace")
            checks["new_analysis_sheets_present"]=all(name in workbook_xml for name in ("评论热度预分析","家居类采集诊断"))
            details["native_hyperlinks"]=sum(
                archive.read(name).count(b"relationships/hyperlink")
                for name in archive.namelist()
                if name.startswith("xl/worksheets/_rels/") and name.endswith(".rels")
            )
    else:
        checks["new_analysis_sheets_present"]=False
    checks["ozon_links_clickable"]=details["native_hyperlinks"]>=details.get("real_products",1)
    details["daily_xlsx"]=str(xlsx_path)
    status="PASS" if all(checks.values()) else "FAIL"
    report=ROOT/"reports"/"health_check.md"
    lines=["# V2 健康检查","",f"- 检查时间：{datetime.now().astimezone().isoformat()}",f"- 总体结果：{status}",f"- REAL 商品：{details.get('real_products',0)}",f"- REAL 快照：{details.get('real_snapshots',0)}",f"- 潜力TOP20：{details.get('potential_top20_rows',0)}（唯一ID {details.get('potential_unique_ids',0)}）",f"- 覆盖家居一级类目：{details.get('categories_covered',0)}/10",f"- 可点击 Ozon 链接：{details.get('native_hyperlinks',0)}",f"- 可用真实原价：{details.get('original_price_count',0)}",f"- 可用真实图片：{details.get('image_count',0)}（公开源未提供时保持空值，不生成或伪造）",f"- RUB/CNY：{details.get('rub_cny')}",f"- 每日统一 Excel：{xlsx_path}","","## 检查项"]
    lines += [f"- {'通过' if value else '失败'}：{name}" for name,value in checks.items()]
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"status":status,"checks":checks,"details":details,"report":str(report)},ensure_ascii=False,indent=2)); return 0 if status=="PASS" else 1


if __name__=="__main__": raise SystemExit(main())
