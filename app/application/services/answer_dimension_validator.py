# app/application/services/answer_dimension_validator.py

import re
from enum import StrEnum


class AnswerDimension(StrEnum):
    """Поддерживаемые физические размерности ответа."""

    PRESSURE = "pressure"
    TEMPERATURE = "temperature"
    HEAT_LOAD = "heat_load"
    FLOW = "flow"
    DIAMETER = "diameter"
    VOLUME = "volume"
    ELECTRICAL = "electrical"


class AnswerDimensionValidator:
    """Дешёвая deterministic-проверка единиц ответа.

    Сервис не пытается понять весь инженерный смысл документа.

    Он предотвращает очевидно несовместимые ответы, например:

        вопрос о давлении
        -> "3~400В 50Гц"

        вопрос о диаметре
        -> "окрашен красной эмалью ПФ-115"

    Если в числовом ответе единица вообще не указана,
    ответ не блокируется, кроме вопросов о диаметре.
    Это сохраняет значения вроде "857,66", когда единица
    уже однозначно задана формулировкой вопроса.
    """

    _NUMBER_RE = re.compile(
        r"\d+(?:[.,]\d+)?"
    )

    _NUMERIC_EXPRESSION_RE = re.compile(
        r"^[\s\d.,;/:\\\-–—≈~]+$"
    )

    _UNIT_PATTERNS = {
        AnswerDimension.PRESSURE: (
            re.compile(
                r"\bмпа\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bкпа\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bбар\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"кгс\s*/\s*см(?:2|²)",
                re.IGNORECASE,
            ),
            re.compile(
                r"м\s*\.?\s*в\s*\.?\s*ст",
                re.IGNORECASE,
            ),
        ),
        AnswerDimension.TEMPERATURE: (
            re.compile(
                r"°\s*[cс]",
                re.IGNORECASE,
            ),
            re.compile(
                r"град\s*\.?\s*[cс]",
                re.IGNORECASE,
            ),
        ),
        AnswerDimension.HEAT_LOAD: (
            re.compile(
                r"гкал\s*/\s*ч",
                re.IGNORECASE,
            ),
            re.compile(
                r"ккал\s*/\s*ч",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bквт\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bмвт\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bвт\b",
                re.IGNORECASE,
            ),
        ),
        AnswerDimension.FLOW: (
            re.compile(
                r"м(?:3|³)\s*/\s*ч",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bт\s*/\s*ч\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"кг\s*/\s*ч",
                re.IGNORECASE,
            ),
            re.compile(
                r"л\s*/\s*с",
                re.IGNORECASE,
            ),
            re.compile(
                r"л\s*/\s*мин",
                re.IGNORECASE,
            ),
        ),
        AnswerDimension.DIAMETER: (
            re.compile(
                r"(?:∅|ø)\s*\d",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:dn|ду)\s*[-:]?\s*\d",
                re.IGNORECASE,
            ),
            re.compile(
                r"\d+(?:[.,]\d+)?\s*мм\b",
                re.IGNORECASE,
            ),
        ),
        AnswerDimension.VOLUME: (
            re.compile(
                r"\bм(?:3|³)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bл\b",
                re.IGNORECASE,
            ),
        ),
        AnswerDimension.ELECTRICAL: (
            re.compile(
                r"\d+(?:[.,]\d+)?\s*[вv](?!т)",
                re.IGNORECASE,
            ),
            re.compile(
                r"\d+(?:[.,]\d+)?\s*(?:гц|hz)",
                re.IGNORECASE,
            ),
        ),
    }

    def is_valid(
        self,
        *,
        question: str,
        answer: str,
    ) -> bool:
        """Проверить физическую совместимость вопроса и ответа."""
        if not answer.strip():
            return True

        expected = self._detect_expected_dimension(
            question
        )

        if expected is None:
            return True

        if not self._NUMBER_RE.search(
            answer
        ):
            return False

        present_dimensions = (
            self._detect_answer_dimensions(
                answer
            )
        )

        if present_dimensions:
            return (
                expected
                in present_dimensions
            )

        # Диаметр особенно легко перепутать с описанием
        # трубы/кабеля/окраски, поэтому для него требуем
        # либо diameter marker, либо чисто числовой ответ.
        if expected == AnswerDimension.DIAMETER:
            return bool(
                self._NUMERIC_EXPRESSION_RE.fullmatch(
                    answer.strip()
                )
            )

        # Для остальных физических величин числовой ответ
        # без явной единицы разрешён: единица часто уже
        # содержится в самом вопросе/табличном заголовке.
        return True

    @staticmethod
    def _detect_expected_dimension(
        question: str,
    ) -> AnswerDimension | None:
        """Определить ожидаемую размерность по формулировке вопроса."""
        normalized = (
            question
            .casefold()
            .replace(
                "ё",
                "е",
            )
        )

        if "давлен" in normalized:
            return AnswerDimension.PRESSURE

        if "температур" in normalized:
            return AnswerDimension.TEMPERATURE

        if (
            "теплов" in normalized
            and "нагруз" in normalized
        ):
            return AnswerDimension.HEAT_LOAD

        if "расход" in normalized:
            return AnswerDimension.FLOW

        if "диаметр" in normalized:
            return AnswerDimension.DIAMETER

        if (
            "объем" in normalized
            or "объём" in question.casefold()
        ):
            return AnswerDimension.VOLUME

        return None

    @classmethod
    def _detect_answer_dimensions(
        cls,
        answer: str,
    ) -> frozenset[AnswerDimension]:
        """Найти явно присутствующие единицы измерения."""
        result = set()

        for dimension, patterns in (
            cls._UNIT_PATTERNS.items()
        ):
            if any(
                pattern.search(
                    answer
                )
                for pattern in patterns
            ):
                result.add(
                    dimension
                )

        return frozenset(
            result
        )
    