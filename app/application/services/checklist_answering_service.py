# app/application/services/checklist_answering_service.py

from app.application.services.grounded_answer_service import (
    GroundedAnswerService,
)
from app.application.services.hybrid_retriever import HybridRetriever
from app.domain.answers import (
    ChecklistAnalysisResult,
    QuestionEvidence,
)
from app.domain.checklists import (
    ChecklistDefinition,
    ChecklistQuestion,
)
from app.domain.retrieval import DocumentChunk


class ChecklistAnsweringService:
    """Заполняет один checklist только evidence из документа.

    Retrieval query намеренно содержит больше контекста, чем
    пользовательский вопрос:

        section title
        + normalized checklist label
        + original question

    Это помогает semantic/lexical retrieval находить формулировки,
    отличающиеся от текста исходного Excel-вопроса.

    Сам LLM при этом получает оригинальный question_text,
    поэтому дополнительный retrieval context не превращается
    в искусственный answer evidence.
    """

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

        retrieval_queries = tuple(
            self._build_retrieval_query(
                section_title=section_title,
                question=question,
            )
            for section_title, question
            in question_entries
        )

        retrieval_results = (
            await self._retriever.retrieve_many(
                retrieval_queries,
                index,
            )
        )

        evidence_items = tuple(
            QuestionEvidence(
                question_id=question.id,
                question_text=question.text,
                hits=retrieval.hits,
            )
            for (
                _,
                question,
            ), retrieval in zip(
                question_entries,
                retrieval_results,
                strict=True,
            )
        )

        answers = []

        for start in range(
            0,
            len(evidence_items),
            self._answer_batch_size,
        ):
            batch = evidence_items[
                start:
                start + self._answer_batch_size
            ]

            answers.extend(
                await self._answer_service.extract(
                    batch
                )
            )

        return ChecklistAnalysisResult(
            checklist_code=checklist.code,
            answers=tuple(answers),
        )

    @staticmethod
    def _build_retrieval_query(
        *,
        section_title: str,
        question: ChecklistQuestion,
    ) -> str:
        """Добавить к embedding query семантический контекст чек-листа."""
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
