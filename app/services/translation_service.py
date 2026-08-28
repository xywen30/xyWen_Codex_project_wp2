from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.mymemory.translated.net/get"
SEPARATOR = " || "

PRODUCT_TYPES = (
    ("средство для мытья посуды", "洗洁精"),
    ("стиральный порошок", "洗衣粉"),
    ("порошок стиральный", "洗衣粉"),
    ("гель для стирки", "洗衣液"),
    ("постельное белье", "床上用品套装"),
    ("полотенце", "毛巾/浴巾"),
    ("одеяло", "被子"),
    ("сушилка для посуды", "餐具沥水架"),
    ("органайзер для кухни", "厨房收纳架"),
    ("коробка для хранения обуви", "鞋盒收纳箱"),
    ("коробка для хранения", "收纳盒"),
    ("контейнер для хранения", "储物箱"),
    ("ваза для цветов", "花瓶"),
    ("насыпные свечи", "颗粒蜡烛材料套装"),
    ("ароматическая свеча", "香薰蜡烛"),
    ("светодиодная лента", "LED灯带"),
    ("светильник-ночник", "硅胶小夜灯"),
    ("настольная лампа", "台灯"),
    ("вешалка-плечики", "衣架"),
    ("полка", "置物隔板"),
    ("кашпо для цветов", "花盆"),
    ("кашпо", "花盆"),
    ("аромадиффузор", "香薰机"),
    ("увлажнитель воздуха", "空气加湿器"),
    ("товары для дома", "家居用品"),
)

DESCRIPTORS = (
    ("для цветного белья", "适合彩色衣物"),
    ("концентрат", "浓缩型"),
    ("автомат", "机洗"),
    ("всесезон", "四季通用"),
    ("махров", "毛圈材质"),
    ("хлопок", "棉质"),
    ("полисатин", "聚缎面料"),
    ("лебяжий пух", "仿天鹅绒填充"),
    ("алоэ вера", "芦荟香型"),
    ("графит", "石墨灰"),
    ("бордо", "酒红色"),
    ("розов", "粉色"),
    ("бел", "白色"),
    ("черн", "黑色"),
    ("сер", "灰色"),
    ("беж", "米色"),
    ("син", "蓝色"),
    ("зелен", "绿色"),
)

BRAND_STOPWORDS = {
    "color", "colour", "parfum", "automatic", "auto", "home", "house",
    "premium", "new", "soft", "original", "max", "pro",
}


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _product_type(title: str, keyword: str = "") -> str:
    haystack = f"{keyword} {title}".lower()
    for token, translated in PRODUCT_TYPES:
        if token in haystack:
            return translated
    return "家居商品"


def _specifications(title: str) -> list[str]:
    specs: list[str] = []
    for match in re.findall(r"\d+(?:[.,]\d+)?\s*[xх×]\s*\d+(?:[.,]\d+)?\s*(?:см|cm)?", title, flags=re.I):
        value = re.sub(r"\s+", "", match).replace("х", "×").replace("x", "×").replace("см", "厘米").replace("cm", "厘米")
        specs.append(value)
    unit_map = {"кг": "公斤", "мл": "毫升", "л": "升", "г": "克", "шт": "件", "стирок": "次洗涤"}
    for number, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(кг|мл|л|г|шт|стирок)\b", title, flags=re.I):
        value = f"{number.replace(',', '.')}{unit_map[unit.lower()]}"
        if value not in specs:
            specs.append(value)
    return specs[:4]


def _brands(title: str) -> list[str]:
    output: list[str] = []
    for token in re.findall(r"(?<![А-Яа-яЁё])[A-Za-z][A-Za-z0-9&+.'-]*", title):
        if token.lower() in BRAND_STOPWORDS or len(token) < 2 or re.fullmatch(r"x\d+", token, flags=re.I):
            continue
        if token not in output:
            output.append(token)
    return output[:3]


def fallback_title_cn(title: str, keyword: str = "") -> str:
    """Produce a concise, honest Chinese identification when remote translation is unavailable."""
    if not title:
        return "家居商品（名称缺失）"
    if _contains_chinese(title):
        return title
    lower = title.lower()
    details = _brands(title) + _specifications(title)
    details.extend(translated for token, translated in DESCRIPTORS if token in lower)
    details = list(dict.fromkeys(details))
    product_type = _product_type(title, keyword)
    return product_type if not details else f"{product_type}｜{'，'.join(details)}"


def _normalize_remote_translation(value: str, title: str, keyword: str) -> str:
    value = re.sub(r"\s+", " ", html.unescape(value or "")).strip()
    if not value or value.lower() == title.lower() or "QUERY LENGTH LIMIT" in value.upper():
        return fallback_title_cn(title, keyword)
    product_type = _product_type(title, keyword)
    if product_type == "洗衣粉":
        value = value.replace("粉末洗衣机", "机洗洗衣粉").replace("洗衣液", "洗衣粉").replace("洗涤粉", "洗衣粉")
    elif product_type == "被子":
        value = value.replace("卧室毯子", "双人被").replace("毯子", "被子")
    elif product_type == "洗洁精":
        value = value.replace("洗碗产品", "洗洁精").replace("洗碗剂", "洗洁精")
    if product_type not in value:
        value = f"{product_type}｜{value}"
    return value[:300]


def _load_cache(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _remote_batches(titles: list[str], budget: int) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    used = 0
    for title in titles:
        if used + len(title) > budget:
            break
        candidate = SEPARATOR.join([*current, title])
        if current and len(candidate.encode("utf-8")) > 450:
            batches.append(current)
            current = [title]
        else:
            current.append(title)
        used += len(title)
    if current:
        batches.append(current)
    return batches


def translate_product_titles(root: Path, rows: list[dict], source: str = "REAL") -> dict:
    """Add title_cn to rows. Remote calls are low-frequency and only send public product titles."""
    cache_path = Path(root) / "data" / "cache" / "title_translations_ru_zh.json"
    cache = _load_cache(cache_path)
    titles = list(dict.fromkeys(str(row.get("title") or "").strip() for row in rows if row.get("title")))
    title_to_keyword = {str(row.get("title") or "").strip(): str(row.get("search_keywords") or "") for row in rows}
    missing = [title for title in titles if not _contains_chinese(title) and title not in cache]
    remote_count = 0
    errors: list[str] = []
    enabled = source == "REAL" and os.getenv("OZON_TRANSLATION_REMOTE", "1").lower() not in {"0", "false", "no"}
    budget = max(0, int(os.getenv("OZON_TRANSLATION_CHAR_BUDGET", "4500")))
    if enabled and missing and budget:
        for batch in _remote_batches(missing, budget):
            try:
                url = f"{API_URL}?{urlencode({'q': SEPARATOR.join(batch), 'langpair': 'ru|zh-CN', 'mt': '1'})}"
                request = Request(url, headers={"User-Agent": "OzonTrendRadar/2.0 (public-title-translation)"})
                with urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                translated = str(payload.get("responseData", {}).get("translatedText") or "")
                parts = [part.strip() for part in translated.split("||")]
                if len(parts) != len(batch):
                    raise ValueError("翻译接口未保留批量分隔符")
                for title, value in zip(batch, parts):
                    keyword = title_to_keyword.get(title, "")
                    normalized = _normalize_remote_translation(value, title, keyword)
                    cache[title] = {"zh": normalized, "source": "MyMemory公开翻译接口", "updated_at": datetime.now().astimezone().isoformat()}
                    remote_count += 1
            except Exception as exc:  # Network failure must not block the daily report.
                errors.append(f"{type(exc).__name__}: {exc}")
                break
        if remote_count:
            _save_cache(cache_path, cache)

    fallback_count = 0
    for row in rows:
        title = str(row.get("title") or "").strip()
        keyword = str(row.get("search_keywords") or "")
        if _contains_chinese(title):
            translated = title
        elif title in cache and cache[title].get("zh"):
            translated = _normalize_remote_translation(str(cache[title]["zh"]), title, keyword)
        else:
            translated = fallback_title_cn(title, keyword)
            fallback_count += 1
        row["title_cn"] = translated
    return {"total": len(rows), "cached_or_remote": len(rows) - fallback_count, "remote_new": remote_count, "fallback": fallback_count, "errors": errors[:3], "cache": str(cache_path)}
