# app/application/services/checklist_answering_service.py

import re

from app.application.services.grounded_answer_service import (
    GroundedAnswerService,
)
from app.application.services.hybrid_retriever import HybridRetriever
from app.domain.answers import (
    AnswerStatus,
    ChecklistAnalysisResult,
    GroundedAnswer,
    QuestionEvidence,
)
from app.domain.checklists import (
    ChecklistDefinition,
    ChecklistQuestion,
)
from app.domain.retrieval import (
    DocumentChunk,
    RetrievalHit,
)


class ChecklistAnsweringService:
    """Заполняет checklist только evidence из документа.

    Pipeline:

        retrieval
            ↓
        deterministic extraction для явно размеченных полей
            ↓
        LLM только для оставшихся вопросов
            ↓
        grounding validation

    Контекст вопроса содержит:

        section title
        + normalized checklist label
        + original question

    Один и тот же контекст используется:

    - для semantic/lexical retrieval;
    - для понимания смысла вопроса answer-моделью.

    Сам section/label не является evidence и не может быть
    источником ответа.

    Некоторые явно размеченные поля можно безопасно извлечь
    детерминированно. Например:

        Наименование объекта: ...
        Абонент: ...

    В таких случаях LLM не должна повторно угадывать,
    какое из нескольких названий документа является объектом.
    """

    _OBJECT_NAME_PATTERNS = (
        re.compile(
            (
                r"(?im)"
                r"^[ \t]*"
                r"наименование[ \t]+"
                r"(?:проектируемого[ \t]+)?"
                r"объекта"
                r"[ \t]*"
                r"[:\-–—]"
                r"[ \t]*"
                r"(?:\r?\n[ \t]*)?"
                r"(?P<value>[^\r\n]+)"
            )
        ),
        re.compile(
            (
                r"(?im)"
                r"^[ \t]*"
                r"абонент"
                r"[ \t]*"
                r"[:\-–—]"
                r"[ \t]*"
                r"(?:\r?\n[ \t]*)?"
                r"(?P<value>[^\r\n]+)"
            )
        ),
    )

    def __init__(
        self,
        *,
        retriever: HybridRetriever,
        answer_service: GroundedAnswerService,
        answer_batch_size: int,
    ) -> None:
        if answer_batch_size <= 0:
            raise ValueError(
                "answer_batch_size must be positive"
            )

        self._retriever = retriever
        self._answer_service = answer_service
        self._answer_batch_size = (
            answer_batch_size
        )

    async def analyze(
        self,
        *,
        checklist: ChecklistDefinition,
        chunks: tuple[DocumentChunk, ...],
    ) -> ChecklistAnalysisResult:
        """Получить grounded answers для всех вопросов checklist."""
        index = await self._retriever.build_index(
            chunks
        )

        question_entries = tuple(
            (
                section.title,
                question,
            )
            for sheet in checklist.sheets
            for section in sheet.sections
            for question in section.questions
        )

        question_contexts = tuple(
            self._build_retrieval_query(
                section_title=section_title,
                question=question,
            )
            for section_title, question
            in question_entries
        )

        retrieval_results = (
            await self._retriever.retrieve_many(
                question_contexts,
                index,
            )
        )

        answers_by_id: dict[
            str,
            GroundedAnswer,
        ] = {}

        unresolved_evidence: list[
            QuestionEvidence
        ] = []

        for (
            _,
            question,
        ), question_context, retrieval in zip(
            question_entries,
            question_contexts,
            retrieval_results,
            strict=True,
        ):
            explicit_answer = (
                self._resolve_explicit_answer(
                    question=question,
                    hits=retrieval.hits,
                )
            )

            if explicit_answer is not None:
                answers_by_id[
                    question.id
                ] = explicit_answer

                continue

            unresolved_evidence.append(
                QuestionEvidence(
                    question_id=question.id,

                    # Section/label помогают понять смысл вопроса,
                    # но ответ по-прежнему разрешён только из hits.
                    question_text=question_context,

                    hits=retrieval.hits,
                )
            )

        evidence_items = tuple(
            unresolved_evidence
        )

        for start in range(
            0,
            len(evidence_items),
            self._answer_batch_size,
        ):
            batch = evidence_items[
                start:
                start + self._answer_batch_size
            ]

            batch_answers = (
                await self._answer_service.extract(
                    batch
                )
            )

            for answer in batch_answers:
                answers_by_id[
                    answer.question_id
                ] = answer

        ordered_answers = tuple(
            answers_by_id[
                question.id
            ]
            for _, question
            in question_entries
        )

        return ChecklistAnalysisResult(
            checklist_code=checklist.code,
            answers=ordered_answers,
        )

    @classmethod
    def _resolve_explicit_answer(
        cls,
        *,
        question: ChecklistQuestion,
        hits: tuple[RetrievalHit, ...],
    ) -> GroundedAnswer | None:
        """Извлечь безопасное явно подписанное поле без LLM.

        Сейчас deterministic extraction применяется только к
        наименованию объекта.

        Это намеренно узкое правило: мы не пытаемся заменить
        LLM регулярными выражениями для всех вопросов.
        """
        if not cls._is_object_name_question(
            question
        ):
            return None

        return cls._resolve_object_name(
            question=question,
            hits=hits,
        )

    @classmethod
    def _resolve_object_name(
        cls,
        *,
        question: ChecklistQuestion,
        hits: tuple[RetrievalHit, ...],
    ) -> GroundedAnswer | None:
        """Получить объект из явно размеченного source field.

        Приоритет:

        1. "Наименование объекта: ..."
        2. "Абонент: ..."

        Внутри каждого варианта сохраняется retrieval ranking.
        """
        for pattern in cls._OBJECT_NAME_PATTERNS:
            for hit in hits:
                match = pattern.search(
                    hit.chunk.text
                )

                if match is None:
                    continue

                value = cls._clean_explicit_value(
                    match.group(
                        "value"
                    )
                )

                if not cls._is_reasonable_explicit_value(
                    value
                ):
                    continue

                supporting_text = (
                    match
                    .group(0)
                    .strip()
                )

                return GroundedAnswer(
                    question_id=question.id,
                    status=AnswerStatus.FOUND,
                    answer=value,
                    confidence=1.0,
                    source_pages=(
                        hit.chunk.page_number,
                    ),
                    supporting_text=supporting_text,
                )

        return None

    @classmethod
    def _is_object_name_question(
        cls,
        question: ChecklistQuestion,
    ) -> bool:
        """Определить вопрос именно о наименовании объекта."""
        parts = [
            question.text,
        ]

        if question.label:
            parts.append(
                question.label
            )

        normalized = cls._normalize_semantic_text(
            " ".join(
                parts
            )
        )

        return (
            "наименование объекта"
            in normalized
            or (
                "наименование проектируемого объекта"
                in normalized
            )
        )

    @staticmethod
    def _clean_explicit_value(
        value: str,
    ) -> str:
        """Очистить значение, не меняя его смысл."""
        normalized = " ".join(
            value.split()
        )

        return normalized.rstrip(
            " \t.;,"
        )

    @staticmethod
    def _is_reasonable_explicit_value(
        value: str,
    ) -> bool:
        """Отбросить пустые и явно повреждённые extraction values."""
        if not value:
            return False

        if len(value) > 300:
            return False

        return True

    @staticmethod
    def _normalize_semantic_text(
        value: str,
    ) -> str:
        """Нормализовать текст только для определения типа поля."""
        return " ".join(
            value
            .casefold()
            .replace(
                "ё",
                "е",
            )
            .split()
        )

    @staticmethod
    def _build_retrieval_query(
        *,
        section_title: str,
        question: ChecklistQuestion,
    ) -> str:
        """Добавить к вопросу семантический контекст чек-листа."""
        parts = [
            section_title.strip(),
        ]

        if question.label:
            label = (
                question.label
                .strip()
                .rstrip(":")
                .strip()
            )

            if label:
                parts.append(
                    label
                )

        parts.append(
            question.text.strip()
        )

        return "\n".join(
            parts
        )
