from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings


def main() -> int:
    updated = invalid = 0
    with sqlite3.connect(settings.database_path) as con:
        rows = con.execute(
            "SELECT id, raw_snippet FROM search_snapshots WHERE data_source='REAL' AND engine='s_shot'"
        ).fetchall()
        for snapshot_id, raw in rows:
            try:
                payload = json.loads(raw)
                old_price = payload.get("old_price")
                image_url = payload.get("image_url") or payload.get("image") or payload.get("picture_url")
                con.execute(
                    "UPDATE search_snapshots SET original_price_rub=?, image_url=? WHERE id=?",
                    (float(old_price) / 100 if old_price is not None else None, image_url, snapshot_id),
                )
                updated += 1
            except (TypeError, ValueError, json.JSONDecodeError):
                invalid += 1
    print({"updated": updated, "invalid": invalid, "source": "已保存的S-SHOT原始公开快照"})
    return 0 if invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
