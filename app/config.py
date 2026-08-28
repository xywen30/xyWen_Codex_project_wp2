from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.category_config import flatten_search_keywords, load_home_categories


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    database_path: Path = ROOT / "database" / "ozon_trend.db"
    timezone: str = "Asia/Shanghai"
    cache_hours: int = 12
    request_timeout: int = 20
    request_delay: float = 1.5
    max_results_per_keyword: int = 10
    direct_ozon_enabled: bool = False

    def ensure(self) -> None:
        dirs = [
            "data/raw", "data/processed", "data/exports", "data/fixtures", "data/cache", "data/screenshots",
            "database/backups", "logs/app", "logs/discovery", "logs/analysis", "logs/errors", "logs/audit",
            "reports/runs", "runtime", "config", "网爬结果",
        ]
        for value in dirs:
            (self.root / value).mkdir(parents=True, exist_ok=True)

    def keywords(self) -> list[dict]:
        matrix_path = self.root / "config" / "home_category_config.json"
        if matrix_path.exists():
            return flatten_search_keywords(load_home_categories(self.root))
        return json.loads((self.root / "config" / "home_keywords.json").read_text(encoding="utf-8"))

    def home_categories(self) -> list[dict]:
        return load_home_categories(self.root)

    def weights(self) -> dict[str, float]:
        data = json.loads((self.root / "config" / "trend_weights.json").read_text(encoding="utf-8"))
        total = sum(float(v) for v in data.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"INVALID_WEIGHT_CONFIG: sum={total}")
        return {k: float(v) for k, v in data.items()}


settings = Settings()
