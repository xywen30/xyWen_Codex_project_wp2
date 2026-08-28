from __future__ import annotations

import json,random,sys
from datetime import date,datetime,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config import settings
from app.database import Database
from app.discovery.deduplicator import deduplicate
from app.models import SearchResult


def generate() -> list[SearchResult]:
    random.seed(20260817); keywords=settings.keywords()[:30]; engines=["google","yandex","bing"]; profiles=["stable","rising","breakout","declining","leader","new","noise"]
    output=[]; today=date.today()
    for i in range(100):
        profile=profiles[i%len(profiles)]; pid=str(9000000000+i); start=0 if profile!="new" else 10
        for day in range(start,15):
            d=today-timedelta(days=14-day); progress=day/14
            base=15+(i%70)
            if profile=="rising": rank=max(1,int(base-35*progress))
            elif profile=="breakout": rank=max(1,int(base-(3 if day<8 else (day-7)*8)))
            elif profile=="declining": rank=min(100,int(base+35*progress))
            elif profile=="leader": rank=1+i%5
            elif profile=="new": rank=max(1,70-(day-start)*14)
            elif profile=="noise": rank=max(1,min(100,base+random.randint(-18,18)))
            else: rank=max(1,base+random.randint(-2,2))
            coverage=1+(day//4 if profile in {"rising","breakout","new"} else 0)
            for k in range(min(coverage,4)):
                kw=keywords[(i+k)%len(keywords)]; engine=engines[(i+day+k)%len(engines)]
                output.append(SearchResult(engine,kw["keyword"],kw["category_cn"],rank+k,f"DEMO {profile} 家居商品 {i+1}",f"https://www.ozon.ru/product/demo-home-{pid}/",f"DEMO profile={profile}",datetime.combine(d,datetime.min.time()).astimezone().isoformat(),"DEMO",price_rub=300+(i%30)*75,rating=round(4.1+(i%9)/10,1),review_count=10+i*7,raw_snippet=f"DEMO profile={profile}"))
    return deduplicate(output)


def main():
    settings.ensure(); db=Database(settings.database_path); db.initialize()
    # DEMO 是可重复生成的测试集。重建前仅清除 DEMO，REAL 数据不受影响。
    with db.connect() as con:
        con.execute("DELETE FROM product_metrics WHERE data_source='DEMO'")
        con.execute("DELETE FROM search_snapshots WHERE data_source='DEMO'")
        con.execute("DELETE FROM products WHERE data_source='DEMO'")
    rows=generate(); result=db.upsert_results(rows)
    fixture=ROOT/"data"/"fixtures"/"demo_generated_summary.json"; fixture.write_text(json.dumps({"data_source":"DEMO","products":100,"snapshots":len(rows),"days":15,"engines":3,"keywords":30},ensure_ascii=False,indent=2),encoding="utf-8")
    print({"new_products":result[0],"snapshots":result[1],"rows":len(rows),"data_source":"DEMO"}); return result


if __name__=="__main__": main()
