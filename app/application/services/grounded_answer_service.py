# app/application/services/grounded_answer_service.py

import re

from app.application.ports.answer_client import AnswerExtractionPort
from app.domain.answers import (
    AnswerCandidate,
    AnswerStatus,
    GroundedAnswer,
    QuestionEvidence,
)


class GroundedAnswerService:
    """Проверяет ответ модели относительно retrieved evidence.

    FOUND принимается только когда:

    - confidence достаточно высокий;
    - присутствует supporting_text;
    - supporting_text реально существует в retrieved chunk;
    - все числа ответа существуют в supporting_text;
    - evidence не относится явно к другой инженерной системе;
    - если вопрос требует конкретный тип учёта, этот тип явно
      присутствует в supporting_text.

    Эти проверки намеренно узкие: application layer не пытается
    повторно интерпретировать весь естественный язык после LLM.
    """

    _NUMBER_RE = re.compile(
        r"\d+(?:[.,]\d+)?"
    )

    _SUBJECT_MARKERS = {
        "heating": (
            "отоплен",
            "qот",
            "gот",
        ),
        "ventilation": (
            "вентил",
            "qвент",
            "gвент",
        ),
        "hot_water": (
            "гвс",
            "горяч",
            "qгвс",
            "gгвс",
        ),
        "cold_water": (
            "хвс",
            "холодн",
        ),
        "technology": (
            "технолог",
        ),
    }

    _ACCOUNTING_RELATION_MARKERS = {
        "common": (
            "общийучет",
            "общегоучета",
            "общемучете",
            "единыйучет",
            "единогоучета",
            "совместныйучет",
            "совместногоучета",
        ),
        "separate": (
            "отдельныйучет",
            "отдельногоучета",
            "отдельномучете",
            "раздельныйучет",
            "раздельногоучета",
            "раздельномучете",
        ),
    }

    def __init__(
        self,
        *,
        answer_client: AnswerExtractionPort,
        found_min_confidence: float,
    ) -> None:
        if not 0 <= found_min_confidence <= 1:
            raise ValueError(
                "found_min_confidence must be between 0 and 1"
            )

        self._answer_client = answer_client
        self._found_min_confidence = (
            found_min_confidence
        )

    async def extract(
        self,
        items: tuple[QuestionEvidence, ...],
    ) -> tuple[GroundedAnswer, ...]:
        """Получить и детерминированно проверить ответы."""
        if not items:
            return ()

        without_evidence = {
            item.question_id
            for item in items
            if not item.hits
        }

        with_evidence = tuple(
            item
            for item in items
            if item.hits
        )

        candidates: tuple[
            AnswerCandidate,
            ...,
        ] = ()

        if with_evidence:
            candidates = (
                await self._answer_client.extract(
                    with_evidence
                )
            )

        candidate_map = self._build_candidate_map(
            candidates,
            with_evidence,
        )

        results: list[
            GroundedAnswer
        ] = []

        for item in items:
            if item.question_id in without_evidence:
                results.append(
                    GroundedAnswer(
                        question_id=item.question_id,
                        status=AnswerStatus.NOT_FOUND,
                        confidence=0.0,
                    )
                )
                continue

            candidate = candidate_map[
                item.question_id
            ]

            results.append(
                self._validate_candidate(
                    item,
                    candidate,
                )
            )

        return tuple(
            results
        )

    @staticmethod
    def _build_candidate_map(
        candidates: tuple[AnswerCandidate, ...],
        requested: tuple[QuestionEvidence, ...],
    ) -> dict[str, AnswerCandidate]:
        """Проверить полноту ответа LLM."""
        candidate_map = {
            candidate.question_id: candidate
            for candidate in candidates
        }

        if len(candidate_map) != len(candidates):
            raise ValueError(
                "Answer client returned duplicate question ids"
            )

        expected_ids = {
            item.question_id
            for item in requested
        }

        if set(candidate_map) != expected_ids:
            raise ValueError(
                "Answer client returned unexpected question ids"
            )

        return candidate_map

    def _validate_candidate(
        self,
        evidence: QuestionEvidence,
        candidate: AnswerCandidate,
    ) -> GroundedAnswer:
        """Превратить untrusted candidate в grounded answer."""
        if candidate.status == AnswerStatus.NOT_FOUND:
            return GroundedAnswer(
                question_id=evidence.question_id,
                status=AnswerStatus.NOT_FOUND,
                confidence=candidate.confidence,
            )

        if candidate.status == AnswerStatus.LOW_CONFIDENCE:
            return GroundedAnswer(
                question_id=evidence.question_id,
                status=AnswerStatus.LOW_CONFIDENCE,
                confidence=candidate.confidence,
            )

        if (
            not candidate.answer
            or not candidate.supporting_text
        ):
            return self._low_confidence(
                evidence,
                candidate,
            )

        if (
            candidate.confidence
            < self._found_min_confidence
        ):
            return self._low_confidence(
                evidence,
                candidate,
            )

        matching_pages = self._find_supporting_pages(
            evidence,
            candidate.supporting_text,
        )

        if not matching_pages:
            return self._low_confidence(
                evidence,
                candidate,
            )

        if not self._numbers_are_grounded(
            candidate.answer,
            candidate.supporting_text,
        ):
            return self._low_confidence(
                evidence,
                candidate,
            )

        if not self._subject_is_grounded(
            evidence.question_text,
            candidate.supporting_text,
        ):
            return self._low_confidence(
                evidence,
                candidate,
            )

        if not self._accounting_relation_is_grounded(
            evidence.question_text,
            candidate.supporting_text,
        ):
            return self._low_confidence(
                evidence,
                candidate,
            )

        return GroundedAnswer(
            question_id=evidence.question_id,
            status=AnswerStatus.FOUND,
            answer=candidate.answer.strip(),
            confidence=candidate.confidence,
            source_pages=matching_pages,
            supporting_text=(
                candidate.supporting_text.strip()
            ),
        )

    def _low_confidence(
        self,
        evidence: QuestionEvidence,
        candidate: AnswerCandidate,
    ) -> GroundedAnswer:
        """Вернуть безопасный пустой результат."""
        source_pages: tuple[int, ...] = ()

        if candidate.supporting_text:
            source_pages = self._find_supporting_pages(
                evidence,
                candidate.supporting_text,
            )

        return GroundedAnswer(
            question_id=evidence.question_id,
            status=AnswerStatus.LOW_CONFIDENCE,
            confidence=candidate.confidence,
            source_pages=source_pages,
        )

    @classmethod
    def _find_supporting_pages(
        cls,
        evidence: QuestionEvidence,
        supporting_text: str,
    ) -> tuple[int, ...]:
        """Найти страницы с реальным supporting_text."""
        needle = cls._normalize(
            supporting_text
        )

        if not needle:
            return ()

        pages = {
            hit.chunk.page_number
            for hit in evidence.hits
            if needle
            in cls._normalize(
                hit.chunk.text
            )
        }

        return tuple(
            sorted(
                pages
            )
        )

    @classmethod
    def _numbers_are_grounded(
        cls,
        answer: str,
        supporting_text: str,
    ) -> bool:
        """Запретить числа, отсутствующие в evidence."""
        answer_numbers = {
            cls._normalize_number(
                value
            )
            for value in cls._NUMBER_RE.findall(
                answer
            )
        }

        support_numbers = {
            cls._normalize_number(
                value
            )
            for value in cls._NUMBER_RE.findall(
                supporting_text
            )
        }

        return (
            answer_numbers
            <= support_numbers
        )

    @classmethod
    def _subject_is_grounded(
        cls,
        question: str,
        supporting_text: str,
    ) -> bool:
        """Не переносить значение между явно разными системами."""
        question_subjects = cls._find_subjects(
            question
        )

        if len(question_subjects) != 1:
            return True

        support_subjects = cls._find_subjects(
            supporting_text
        )

        if not support_subjects:
            return True

        return bool(
            question_subjects
            & support_subjects
        )

    @classmethod
    def _accounting_relation_is_grounded(
        cls,
        question: str,
        supporting_text: str,
    ) -> bool:
        """Проверить явное подтверждение общего/отдельного учёта.

        Само присутствие системы в расчёте или схеме не доказывает,
        что эта система относится именно к общему либо отдельному учёту.
        """
        question_relation = (
            cls._find_accounting_relation(
                question
            )
        )

        if question_relation is None:
            return True

        support_relation = (
            cls._find_accounting_relation(
                supporting_text
            )
        )

        return (
            support_relation
            == question_relation
        )

    @classmethod
    def _find_subjects(
        cls,
        value: str,
    ) -> frozenset[str]:
        """Определить только явно названные системы."""
        normalized = cls._compact(
            value
        )

        return frozenset(
            subject
            for subject, markers
            in cls._SUBJECT_MARKERS.items()
            if any(
                marker
                in normalized
                for marker in markers
            )
        )

    @classmethod
    def _find_accounting_relation(
        cls,
        value: str,
    ) -> str | None:
        """Определить явно названный тип учёта."""
        normalized = cls._compact(
            value
        )

        for relation, markers in (
            cls._ACCOUNTING_RELATION_MARKERS.items()
        ):
            if any(
                marker
                in normalized
                for marker in markers
            ):
                return relation

        return None

    @staticmethod
    def _compact(
        value: str,
    ) -> str:
        """Нормализовать строку для поиска технических маркеров."""
        return (
            value
            .casefold()
            .replace(
                "ё",
                "е",
            )
            .replace(
                " ",
                "",
            )
            .replace(
                "\n",
                "",
            )
        )

    @staticmethod
    def _normalize_number(
        value: str,
    ) -> str:
        """Унифицировать десятичный разделитель."""
        return value.replace(
            ",",
            ".",
        )

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """Нормализовать регистр и whitespace."""
        return " ".join(
            value
            .casefold()
            .replace(
                "ё",
                "е",
            )
            .split()
        )
