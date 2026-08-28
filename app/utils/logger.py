from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from .security import redact


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def get_logger(root: Path, module: str) -> logging.Logger:
    logger = logging.getLogger(f"ozon_v2.{module}")
    if logger.handlers:
        return logger
    day = datetime.now().strftime("%Y%m%d")
    folder = root / "logs" / (module if module in {"app", "discovery", "analysis", "errors", "audit"} else "app")
    folder.mkdir(parents=True, exist_ok=True)
    fmt = RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(folder / f"{module}_{day}.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def cleanup_logs(root: Path, keep_days: int = 30) -> None:
    cutoff = datetime.now() - timedelta(days=keep_days)
    for path in (root / "logs").glob("*/*.log"):
        if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
            path.unlink(missing_ok=True)
