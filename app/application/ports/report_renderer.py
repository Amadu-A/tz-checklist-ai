# app/application/ports/report_renderer.py

from typing import Protocol

from app.domain.answers import ChecklistAnalysisResult
from app.domain.checklists import ChecklistDefinition


class ChecklistReportRendererPort(Protocol):
    """Порт формирования конечного PDF-отчёта."""

    def render(
        self,
        *,
        checklist: ChecklistDefinition,
        analysis: ChecklistAnalysisResult,
    ) -> bytes:
        """Сформировать PDF исключительно в памяти."""
        ...
    