# app/domain/checklists.py

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
    VlmFallbackReason,
)


class DomainModel(BaseModel):
    """Базовая строгая и неизменяемая Pydantic-модель домена."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class ClassifierHint(DomainModel):
    """Фраза-маркер для определения подходящего чек-листа."""

    text: str = Field(
        min_length=1
    )

    weight: float = Field(
        default=1.0,
        gt=0,
    )


class ChecklistCatalogEntry(DomainModel):
    """Краткое описание одного чек-листа и признаки его класса."""

    code: ChecklistCode

    title: str = Field(
        min_length=1
    )

    description: str = Field(
        min_length=1
    )

    classifier_hints: tuple[
        ClassifierHint,
        ...,
    ] = Field(
        min_length=1,
    )


class ChecklistCatalog(DomainModel):
    """Каталог всех поддерживаемых сервисом чек-листов."""

    schema_version: int = Field(
        default=1,
        ge=1,
    )

    checklists: tuple[
        ChecklistCatalogEntry,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(
        mode="after"
    )
    def validate_unique_codes(
        self,
    ) -> "ChecklistCatalog":
        """Запретить повторение кода чек-листа в каталоге."""
        codes = [
            item.code
            for item in self.checklists
        ]

        if (
            len(codes)
            != len(
                set(codes)
            )
        ):
            raise ValueError(
                "Checklist catalog "
                "contains duplicate codes"
            )

        return self


class ChecklistQuestion(DomainModel):
    """Один неизменяемый вопрос исходного XLSX-чек-листа."""

    id: str = Field(
        min_length=1
    )

    source_number: str = Field(
        min_length=1
    )

    text: str = Field(
        min_length=1
    )

    output_order: int = Field(
        ge=1
    )

    label: str | None = None

    # Если проблема уже находилась в исходном XLSX,
    # она документируется, но не исправляется скрытно.
    source_issue: str | None = None


class ChecklistSection(DomainModel):
    """Логический раздел вопросов внутри sheet."""

    id: str = Field(
        min_length=1
    )

    title: str = Field(
        min_length=1
    )

    questions: tuple[
        ChecklistQuestion,
        ...,
    ] = Field(
        default_factory=tuple,
    )


class ChecklistSheet(DomainModel):
    """Нормализованное представление одного Excel sheet."""

    id: str = Field(
        min_length=1
    )

    title: str = Field(
        min_length=1
    )

    sections: tuple[
        ChecklistSection,
        ...,
    ] = Field(
        min_length=1,
    )


class ChecklistDefinition(DomainModel):
    """Полное неизменяемое определение одного чек-листа."""

    schema_version: int = Field(
        default=1,
        ge=1,
    )

    code: ChecklistCode

    title: str = Field(
        min_length=1
    )

    description: str = Field(
        min_length=1
    )

    source_workbook: str = Field(
        min_length=1
    )

    expected_question_count: int = Field(
        gt=0
    )

    sheets: tuple[
        ChecklistSheet,
        ...,
    ] = Field(
        min_length=1,
    )

    @property
    def questions(
        self,
    ) -> tuple[
        ChecklistQuestion,
        ...,
    ]:
        """Вернуть все вопросы в исходном порядке sheets и sections."""
        return tuple(
            question
            for sheet in self.sheets
            for section in sheet.sections
            for question in section.questions
        )

    @model_validator(
        mode="after"
    )
    def validate_question_structure(
        self,
    ) -> "ChecklistDefinition":
        """Проверить количество вопросов и уникальность внутренних id."""
        questions = (
            self.questions
        )

        if (
            len(questions)
            != self.expected_question_count
        ):
            raise ValueError(
                "Checklist question "
                "count mismatch: "
                f"expected="
                f"{self.expected_question_count}, "
                f"actual="
                f"{len(questions)}"
            )

        ids = [
            question.id
            for question
            in questions
        ]

        if (
            len(ids)
            != len(
                set(ids)
            )
        ):
            raise ValueError(
                "Checklist contains "
                "duplicate question ids"
            )

        return self


class ChecklistScore(DomainModel):
    """Скоринг одного кандидата при классификации документа."""

    code: ChecklistCode

    score: float = Field(
        ge=0
    )

    matched_hints: tuple[
        str,
        ...,
    ] = Field(
        default_factory=tuple,
    )


class ChecklistSuggestion(DomainModel):
    """Рекомендация сервиса, ожидающая подтверждения пользователя.

    recommended_code может быть None, если сервис не обнаружил
    ни одного содержательного классификационного признака.

    Это безопаснее, чем автоматически выбирать первый чек-лист
    только из-за его позиции в каталоге.
    """

    recommended_code: (
        ChecklistCode
        | None
    )

    confidence: float = Field(
        ge=0,
        le=1,
    )

    ranking: tuple[
        ChecklistScore,
        ...,
    ] = Field(
        min_length=1,
    )

    requires_confirmation: bool = True


class ConfirmedChecklist(DomainModel):
    """Явно подтверждённый пользователем чек-лист."""

    code: ChecklistCode

    title: str = Field(
        min_length=1
    )


class ChecklistSelectionResult(DomainModel):
    """Полный результат автоматического выбора чек-листа.

    Содержит саму рекомендацию и диагностическую информацию
    о том, пришлось ли использовать VLM fallback.
    """

    suggestion: ChecklistSuggestion

    source: ClassificationSource

    fallback_reason: (
        VlmFallbackReason
        | None
    ) = None

    vision_pages: tuple[
        int,
        ...,
    ] = Field(
        default_factory=tuple,
    )

    @model_validator(
        mode="after"
    )
    def validate_fallback_metadata(
        self,
    ) -> "ChecklistSelectionResult":
        """Проверить согласованность source и VLM-метаданных."""
        if (
            self.source
            == ClassificationSource.NATIVE_TEXT
        ):
            if (
                self.fallback_reason
                is not None
            ):
                raise ValueError(
                    "Native-text result "
                    "cannot contain "
                    "VLM fallback reason"
                )

            if self.vision_pages:
                raise ValueError(
                    "Native-text result "
                    "cannot contain "
                    "VLM page numbers"
                )

        if (
            self.source
            == ClassificationSource.NATIVE_TEXT_AND_VLM
        ):
            if (
                self.fallback_reason
                is None
            ):
                raise ValueError(
                    "VLM result must contain "
                    "fallback reason"
                )

            if not self.vision_pages:
                raise ValueError(
                    "VLM result must contain "
                    "analyzed page numbers"
                )

        return self
