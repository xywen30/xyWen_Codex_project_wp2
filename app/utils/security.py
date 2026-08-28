from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


SENSITIVE = re.compile(r"(?i)(cookie|authorization|token|session|api[-_ ]?key|password|proxy[-_ ]?credential)\s*[:=]\s*([^\s;,]+)")


def redact(value: object) -> str:
    return SENSITIVE.sub(lambda m: f"{m.group(1)}=[REDACTED]", str(value))


def safe_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return "[INVALID_URL]"
