# app/domain/enums.py

from enum import StrEnum


class ChecklistCode(StrEnum):
    """Стабильные коды пяти поддерживаемых чек-листов."""

    UUTE = "UUTE"
    ITP = "ITP"
    MKBI = "MKBI"
    SPD = "SPD"
    AUPT = "AUPT"


class ClassificationSource(StrEnum):
    """Источник данных, использованный при выборе чек-листа."""

    NATIVE_TEXT = "native_text"
    NATIVE_TEXT_AND_VLM = "native_text_and_vlm"


class VlmFallbackReason(StrEnum):
    """Причина подключения VLM к классификации."""

    INSUFFICIENT_NATIVE_TEXT = "insufficient_native_text"
    LOW_CONFIDENCE = "low_confidence"


class JobStatus(StrEnum):
    """Состояние фонового анализа.

    AWAITING_CONFIRMATION означает, что исходный PDF уже принят,
    но пользователь ещё не подтвердил предложенный чек-лист.

    QUEUED означает, что задание отправлено в RabbitMQ.

    PROCESSING означает, что Celery worker уже начал анализ.

    COMPLETED означает, что временный PDF-отчёт готов к одноразовой
    выдаче клиенту.

    FAILED означает, что обработка завершилась ошибкой.
    """

    AWAITING_CONFIRMATION = "awaiting_confirmation"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"