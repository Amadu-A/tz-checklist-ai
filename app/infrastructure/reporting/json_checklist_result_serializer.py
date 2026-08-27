# app/infrastructure/reporting/json_checklist_result_serializer.py

from app.domain.results import ChecklistJsonResult


class JsonChecklistResultSerializer:
    """Сериализует публичный результат в UTF-8 JSON."""

    def serialize(
        self,
        result: ChecklistJsonResult,
    ) -> bytes:
        """Получить валидный JSON без промежуточных файлов."""
        return (
            result
            .model_dump_json()
            .encode(
                "utf-8"
            )
        )
