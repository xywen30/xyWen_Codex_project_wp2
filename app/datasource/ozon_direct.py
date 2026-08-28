from __future__ import annotations

from datetime import datetime, timezone

from app.models import SourceDiagnostic


class OzonDirectSource:
    name = "ozon_direct"

    def __init__(self, enabled: bool = False): self.enabled=enabled

    def diagnose(self) -> SourceDiagnostic:
        reason="KNOWN_403_CIRCUIT_OPEN" if not self.enabled else "NOT_TESTED"
        return SourceDiagnostic(self.name,"BLOCKED",403,"text/html",0,0,0,reason,datetime.now(timezone.utc).isoformat(),"https://www.ozon.ru/")

    def discover(self, keyword: dict): return []
