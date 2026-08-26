# app/application/services/checklist_answering_service.py

from app.application.services.grounded_answer_service import (
    GroundedAnswerService,
)
from app.application.services.hybrid_retriever import HybridRetriever
from app.domain.answers import (
    ChecklistAnalysisResult,
    QuestionEvidence,
)
from app.domain.checklists import ChecklistDefinition
from app.domain.retrieval import DocumentChunk


class ChecklistAnsweringService:
    """Заполняет один checklist только evidence из документа."""

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

        questions = checklist.questions

        retrieval_results = (
            await self._retriever.retrieve_many(
                tuple(
                    question.text
                    for question in questions
                ),
                index,
            )
        )

        evidence_items = tuple(
            QuestionEvidence(
                question_id=question.id,
                question_text=question.text,
                hits=retrieval.hits,
            )
            for question, retrieval in zip(
                questions,
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
    