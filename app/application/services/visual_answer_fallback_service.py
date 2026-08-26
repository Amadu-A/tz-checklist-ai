# app/application/services/visual_answer_fallback_service.py

from pathlib import Path

from app.application.services.document_chunker import DocumentChunker
from app.application.services.document_content_service import DocumentContentService
from app.application.services.grounded_answer_service import GroundedAnswerService
from app.application.services.hybrid_retriever import HybridRetriever
from app.domain.answers import (
    AnswerStatus,
    ChecklistAnalysisResult,
    GroundedAnswer,
    QuestionEvidence,
)
from app.domain.checklists import ChecklistDefinition
from app.domain.documents import (
    DocumentTextContext,
    PdfPageText,
)


class VisualAnswerFallbackService:
    """Подключает VLM только для unresolved-вопросов.

    Native text остаётся главным источником.

    Visual fallback используется только когда после обычного
    retrieval + grounded extraction ответ остался NOT_FOUND либо
    LOW_CONFIDENCE.

    В первую очередь анализируются:
    - source pages LOW_CONFIDENCE-ответов;
    - страницы со слабым native text;
    - страницы-сканы и страницы с графикой.

    Все VLM-вызовы выполняются через DocumentContentService,
    который уже гарантирует последовательную обработку страниц.
    """

    def __init__(
        self,
        *,
        content_service: DocumentContentService,
        chunker: DocumentChunker,
        retriever: HybridRetriever,
        answer_service: GroundedAnswerService,
        answer_batch_size: int,
        max_pages: int,
        weak_page_max_chars: int,
    ) -> None:
        if answer_batch_size <= 0:
            raise ValueError(
                "answer_batch_size must be positive"
            )

        if max_pages <= 0:
            raise ValueError(
                "max_pages must be positive"
            )

        if weak_page_max_chars < 0:
            raise ValueError(
                "weak_page_max_chars cannot be negative"
            )

        self._content_service = content_service
        self._chunker = chunker
        self._retriever = retriever
        self._answer_service = answer_service

        self._answer_batch_size = answer_batch_size
        self._max_pages = max_pages
        self._weak_page_max_chars = weak_page_max_chars

    async def enrich(
        self,
        *,
        pdf_path: Path,
        checklist: ChecklistDefinition,
        native_context: DocumentTextContext,
        analysis: ChecklistAnalysisResult,
    ) -> ChecklistAnalysisResult:
        """Попытаться разрешить только незаполненные вопросы."""
        unresolved = tuple(
            answer
            for answer in analysis.answers
            if answer.status != AnswerStatus.FOUND
        )

        if not unresolved:
            return analysis

        page_numbers = self._select_pages(
            native_context=native_context,
            unresolved=unresolved,
        )

        if not page_numbers:
            return analysis

        vision_context = (
            await self._content_service.analyze_visual_pages(
                pdf_path,
                page_numbers=page_numbers,
            )
        )

        vision_pages = tuple(
            PdfPageText(
                page_number=page.page_number,
                text=page.searchable_text,
            )
            for page in vision_context.pages
            if page.searchable_text.strip()
        )

        if not vision_pages:
            return analysis

        visual_text_context = DocumentTextContext(
            pages=vision_pages
        )

        chunks = self._chunker.chunk(
            visual_text_context
        )

        if not chunks:
            return analysis

        question_map = {
            question.id: question
            for question in checklist.questions
        }

        unresolved_questions = tuple(
            question_map[answer.question_id]
            for answer in unresolved
        )

        index = await self._retriever.build_index(
            chunks
        )

        retrieval_results = (
            await self._retriever.retrieve_many(
                tuple(
                    question.text
                    for question in unresolved_questions
                ),
                index,
            )
        )

        evidence = tuple(
            QuestionEvidence(
                question_id=question.id,
                question_text=question.text,
                hits=retrieval.hits,
            )
            for question, retrieval in zip(
                unresolved_questions,
                retrieval_results,
                strict=True,
            )
        )

        fallback_answers: list[GroundedAnswer] = []

        for start in range(
            0,
            len(evidence),
            self._answer_batch_size,
        ):
            batch = evidence[
                start:
                start + self._answer_batch_size
            ]

            fallback_answers.extend(
                await self._answer_service.extract(
                    batch
                )
            )

        fallback_map = {
            answer.question_id: answer
            for answer in fallback_answers
        }

        merged = tuple(
            self._merge_answer(
                original=answer,
                fallback=fallback_map.get(
                    answer.question_id
                ),
            )
            for answer in analysis.answers
        )

        return ChecklistAnalysisResult(
            checklist_code=analysis.checklist_code,
            answers=merged,
        )

    def _select_pages(
        self,
        *,
        native_context: DocumentTextContext,
        unresolved: tuple[GroundedAnswer, ...],
    ) -> tuple[int, ...]:
        """Выбрать небольшой набор visual-кандидатов."""
        selected: list[int] = []

        def append(
            page_number: int,
        ) -> None:
            if page_number in selected:
                return

            if len(selected) >= self._max_pages:
                return

            selected.append(
                page_number
            )

        # LOW_CONFIDENCE может уже знать страницу,
        # на которой была обнаружена спорная информация.
        for answer in unresolved:
            for page_number in answer.source_pages:
                append(
                    page_number
                )

        # Затем добавляем слабые native pages.
        for page in native_context.pages:
            if (
                page.character_count
                > self._weak_page_max_chars
            ):
                continue

            # Полностью пустая физическая страница без картинок
            # VLM не нужна.
            if (
                page.character_count == 0
                and page.image_count == 0
            ):
                continue

            append(
                page.page_number
            )

        return tuple(
            selected
        )

    @staticmethod
    def _merge_answer(
        *,
        original: GroundedAnswer,
        fallback: GroundedAnswer | None,
    ) -> GroundedAnswer:
        """Visual evidence может заменить ответ только на FOUND."""
        if original.status == AnswerStatus.FOUND:
            return original

        if (
            fallback is not None
            and fallback.status == AnswerStatus.FOUND
        ):
            return fallback

        return original
    