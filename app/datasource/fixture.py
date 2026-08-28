from __future__ import annotations

import json
from pathlib import Path

from app.models import SearchResult


class FixtureSource:
    def __init__(self, path: Path): self.path=path
    def load(self) -> list[SearchResult]: return [SearchResult(**row) for row in json.loads(self.path.read_text(encoding="utf-8"))]
