# app/domain/answers.py

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ChecklistCode
from app.domain.retrieval import RetrievalHit


class AnswerStatus(StrEnum):
    """Результат поиска ответа только по пользовательскому документу."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    LOW_CONFIDENCE = "low_confidence"


class AnswerModel(BaseModel):
    """Базовая строгая неизменяемая модель answer-слоя."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class QuestionEvidence(AnswerModel):
    """Вопрос вместе с найденными для него fragments."""

    question_id: str = Field(min_length=1)

    question_text: str = Field(min_length=1)

    hits: tuple[RetrievalHit, ...] = Field(
        default_factory=tuple,
    )


class AnswerCandidate(AnswerModel):
    """Непроверенный структурированный результат LLM.

    supporting_text обязан быть дословным фрагментом evidence.
    Application layer отдельно проверяет это требование.
    """

    question_id: str = Field(min_length=1)

    status: AnswerStatus

    answer: str | None = None

    confidence: float = Field(
        ge=0,
        le=1,
    )

    supporting_text: str | None = None


class GroundedAnswer(AnswerModel):
    """Ответ после deterministic grounding validation."""

    question_id: str = Field(min_length=1)

    status: AnswerStatus

    answer: str | None = None

    confidence: float = Field(
        ge=0,
        le=1,
    )

    source_pages: tuple[int, ...] = Field(
        default_factory=tuple,
    )

    supporting_text: str | None = None

    @property
    def output_answer(self) -> str:
        """Вернуть текст только для надёжно подтверждённого ответа."""
        if (
            self.status == AnswerStatus.FOUND
            and self.answer
        ):
            return self.answer

        return ""

    @model_validator(mode="after")
    def validate_answer_state(self) -> "GroundedAnswer":
        """Запретить вывод неподтверждённого текста."""
        if self.status == AnswerStatus.FOUND:
            if not self.answer:
                raise ValueError(
                    "FOUND answer must contain answer text"
                )

            if not self.supporting_text:
                raise ValueError(
                    "FOUND answer must contain supporting_text"
                )

            if not self.source_pages:
                raise ValueError(
                    "FOUND answer must contain source pages"
                )

            return self

        if self.answer is not None:
            raise ValueError(
                "Non-FOUND answer must not contain answer text"
            )

        return self


class ChecklistAnalysisResult(AnswerModel):
    """Проверенные ответы на весь выбранный чек-лист."""

    checklist_code: ChecklistCode

    answers: tuple[GroundedAnswer, ...]

    @model_validator(mode="after")
    def validate_unique_question_ids(self) -> "ChecklistAnalysisResult":
        """Один вопрос не должен получить несколько итоговых ответов."""
        ids = [
            answer.question_id
            for answer in self.answers
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Analysis result contains duplicate question ids"
            )

        return self
    