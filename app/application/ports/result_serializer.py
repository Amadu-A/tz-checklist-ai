# app/application/ports/result_serializer.py

from typing import Protocol

from app.domain.results import ChecklistJsonResult


class ChecklistResultSerializerPort(Protocol):
    """Порт сериализации готового результата для временной доставки."""

    def serialize(
        self,
        result: ChecklistJsonResult,
    ) -> bytes:
        """Преобразовать результат в bytes для ephemeral storage."""
        ...
