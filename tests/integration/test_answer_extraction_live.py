# tests/integration/test_answer_extraction_live.py

from app.application.services.grounded_answer_service import (
    GroundedAnswerService,
)
from app.core.config import Settings
from app.domain.answers import (
    AnswerStatus,
    QuestionEvidence,
)
from app.domain.retrieval import (
    DocumentChunk,
    RetrievalHit,
)
from app.infrastructure.ai.ollama_answer_client import (
    OllamaAnswerClient,
)


async def test_real_llm_returns_grounded_answer() -> None:
    """Проверить реальный structured grounded extraction."""
    settings = Settings()

    client = OllamaAnswerClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_llm_model,
        keep_alive=settings.ollama_keep_alive,
        timeout_seconds=settings.ollama_request_timeout_seconds,
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=settings.answer_found_min_confidence,
    )

    evidence_text = (
        "Расход теплоносителя составляет 3.93 т/ч."
    )

    result = await service.extract(
        (
            QuestionEvidence(
                question_id="q-test",
                question_text=(
                    "Какой расход теплоносителя?"
                ),
                hits=(
                    RetrievalHit(
                        chunk=DocumentChunk(
                            chunk_id="p1-c1",
                            page_number=1,
                            chunk_index=1,
                            text=evidence_text,
                        ),
                        lexical_score=1,
                        semantic_score=1,
                        hybrid_score=1,
                    ),
                ),
            ),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )

    assert (
        "3.93"
        in result[0].output_answer
    )

    assert (
        result[0].source_pages
        == (1,)
    )
    