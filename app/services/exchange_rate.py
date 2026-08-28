from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree

import httpx


def parse_cbr(xml: str) -> tuple[str, float]:
    root=ElementTree.fromstring(xml)
    node=next((n for n in root.findall("Valute") if n.findtext("CharCode")=="CNY"),None)
    if node is None: raise ValueError("CNY_NOT_FOUND")
    nominal=Decimal(node.findtext("Nominal")); rub_per_cny=Decimal(node.findtext("Value").replace(",","."))/nominal
    rate=(Decimal(1)/rub_per_cny).quantize(Decimal("0.000001"),rounding=ROUND_HALF_UP)
    if not Decimal("0.01")<rate<Decimal("1") or not Decimal("1")<rate*500<Decimal("500"): raise ValueError("RATE_DIRECTION_INVALID")
    d,m,y=root.attrib["Date"].split(".")
    return f"{y}-{m}-{d}",float(rate)


def get_rate(root: Path, target: date | None=None) -> dict:
    cache=root/"data"/"cache"/"cbr_rub_cny.json"; target=target or date.today()-timedelta(days=1)
    url="https://www.cbr.ru/scripts/XML_daily.asp"
    try:
        response=httpx.get(url,params={"date_req":target.strftime("%d/%m/%Y")},timeout=20)
        response.raise_for_status(); rate_date,rate=parse_cbr(response.content.decode("windows-1251"))
        result={"rub_cny":rate,"date":rate_date,"source":"俄罗斯中央银行CBR官方每日汇率","url":str(response.url)}
        cache.parent.mkdir(parents=True,exist_ok=True); cache.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return result
    except Exception:
        if cache.exists(): return json.loads(cache.read_text(encoding="utf-8"))
        raise
