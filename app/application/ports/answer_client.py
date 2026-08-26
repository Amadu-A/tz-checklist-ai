# app/application/ports/answer_client.py

from typing import Protocol

from app.domain.answers import (
    AnswerCandidate,
    QuestionEvidence,
)


class AnswerExtractionPort(Protocol):
    """Порт строгого извлечения ответов из предоставленного evidence."""

    async def extract(
        self,
        items: tuple[QuestionEvidence, ...],
    ) -> tuple[AnswerCandidate, ...]:
        """Извлечь ответы без доступа к исходному PDF целиком."""
        ...
