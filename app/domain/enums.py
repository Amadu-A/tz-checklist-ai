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
    """Причина подключения VLM к классификации документа."""

    INSUFFICIENT_NATIVE_TEXT = "insufficient_native_text"
    LOW_CONFIDENCE = "low_confidence"
