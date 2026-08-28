from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import SearchResult, SourceDiagnostic


class DataSource(ABC):
    name: str

    @abstractmethod
    def diagnose(self) -> SourceDiagnostic: ...

    @abstractmethod
    def discover(self, keyword: dict) -> list[SearchResult]: ...
