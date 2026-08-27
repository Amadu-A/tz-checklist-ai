# app/domain/enums.py

from enum import StrEnum


class ChecklistCode(StrEnum):
    """Стабильные внутренние коды пяти чек-листов."""

    UUTE = "UUTE"
    ITP = "ITP"
    MKBI = "MKBI"
    SPD = "SPD"
    AUPT = "AUPT"


class ChecklistTag(StrEnum):
    """Публичные теги чек-листов для 1С / Telegram / API."""

    UUTE = "УУТЭ"
    ITP = "ИТП"
    MKBI = "МКБИ"
    SPD = "СПД"
    AUPT = "АУПТ"

    @property
    def code(
        self,
    ) -> ChecklistCode:
        """Преобразовать публичный тег во внутренний код."""
        mapping = {
            ChecklistTag.UUTE: ChecklistCode.UUTE,
            ChecklistTag.ITP: ChecklistCode.ITP,
            ChecklistTag.MKBI: ChecklistCode.MKBI,
            ChecklistTag.SPD: ChecklistCode.SPD,
            ChecklistTag.AUPT: ChecklistCode.AUPT,
        }

        return mapping[
            self
        ]

    @classmethod
    def from_code(
        cls,
        code: ChecklistCode,
    ) -> "ChecklistTag":
        """Получить публичный тег по внутреннему коду."""
        mapping = {
            ChecklistCode.UUTE: cls.UUTE,
            ChecklistCode.ITP: cls.ITP,
            ChecklistCode.MKBI: cls.MKBI,
            ChecklistCode.SPD: cls.SPD,
            ChecklistCode.AUPT: cls.AUPT,
        }

        return mapping[
            code
        ]

    @classmethod
    def _missing_(
        cls,
        value: object,
    ) -> "ChecklistTag | None":
        """Разрешить регистр и латинские внутренние коды."""
        if not isinstance(
            value,
            str,
        ):
            return None

        normalized = (
            value
            .strip()
            .casefold()
        )

        aliases = {
            "уутэ": cls.UUTE,
            "uute": cls.UUTE,
            "итп": cls.ITP,
            "itp": cls.ITP,
            "мкби": cls.MKBI,
            "mkbi": cls.MKBI,
            "спд": cls.SPD,
            "spd": cls.SPD,
            "аупт": cls.AUPT,
            "aupt": cls.AUPT,
        }

        return aliases.get(
            normalized
        )


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

    AWAITING_CONFIRMATION:
        PDF принят, но auto-detected checklist ещё не подтверждён.

    QUEUED:
        задание отправлено в RabbitMQ.

    PROCESSING:
        worker выполняет анализ.

    COMPLETED:
        временный JSON-результат готов к одноразовой выдаче.

    FAILED:
        обработка завершилась ошибкой.
    """

    AWAITING_CONFIRMATION = "awaiting_confirmation"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    