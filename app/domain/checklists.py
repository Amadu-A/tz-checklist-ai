# app/domain/checklists.py

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
    VlmFallbackReason,
)


class DomainModel(BaseModel):
    """Базовая Pydantic-модель домена с запретом неизвестных полей."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class ClassifierHint(DomainModel):
    """Фраза-маркер, используемая при определении подходящего чек-листа."""

    text: str = Field(min_length=1)
    weight: float = Field(
        default=1.0,
        gt=0,
    )


class ChecklistCatalogEntry(DomainModel):
    """Краткое описание чек-листа и его признаки для классификации."""

    code: ChecklistCode

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    classifier_hints: tuple[ClassifierHint, ...] = Field(
        min_length=1,
    )


class ChecklistCatalog(DomainModel):
    """Каталог всех доступных в сервисе чек-листов."""

    schema_version: int = Field(
        default=1,
        ge=1,
    )

    checklists: tuple[ChecklistCatalogEntry, ...] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_unique_codes(self) -> "ChecklistCatalog":
        """Запретить повторение одного и того же кода в каталоге."""
        codes = [
            item.code
            for item in self.checklists
        ]

        if len(codes) != len(set(codes)):
            raise ValueError(
                "Checklist catalog contains duplicate codes"
            )

        return self


class ChecklistQuestion(DomainModel):
    """Один неизменяемый вопрос исходного чек-листа."""

    id: str = Field(min_length=1)

    source_number: str = Field(min_length=1)

    text: str = Field(min_length=1)

    output_order: int = Field(ge=1)

    label: str | None = None

    # Если ошибка уже присутствует в исходном XLSX,
    # мы фиксируем её явно, а не исправляем незаметно.
    source_issue: str | None = None


class ChecklistSection(DomainModel):
    """Логический раздел вопросов внутри листа Excel."""

    id: str = Field(min_length=1)

    title: str = Field(min_length=1)

    questions: tuple[ChecklistQuestion, ...] = Field(
        default_factory=tuple,
    )


class ChecklistSheet(DomainModel):
    """Нормализованное представление одного sheet исходного XLSX."""

    id: str = Field(min_length=1)

    title: str = Field(min_length=1)

    sections: tuple[ChecklistSection, ...] = Field(
        min_length=1,
    )


class ChecklistDefinition(DomainModel):
    """Полная неизменяемая структура одного чек-листа."""

    schema_version: int = Field(
        default=1,
        ge=1,
    )

    code: ChecklistCode

    title: str = Field(min_length=1)

    description: str = Field(min_length=1)

    source_workbook: str = Field(min_length=1)

    expected_question_count: int = Field(gt=0)

    sheets: tuple[ChecklistSheet, ...] = Field(
        min_length=1,
    )

    @property
    def questions(self) -> tuple[ChecklistQuestion, ...]:
        """Вернуть вопросы в исходном порядке листов и разделов."""
        return tuple(
            question
            for sheet in self.sheets
            for section in sheet.sections
            for question in section.questions
        )

    @model_validator(mode="after")
    def validate_question_structure(
        self,
    ) -> "ChecklistDefinition":
        """Проверить количество вопросов и глобальную уникальность id."""
        questions = self.questions

        if len(questions) != self.expected_question_count:
            raise ValueError(
                "Checklist question count mismatch: "
                f"expected={self.expected_question_count}, "
                f"actual={len(questions)}"
            )

        ids = [
            question.id
            for question in questions
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Checklist contains duplicate question ids"
            )

        return self


class ChecklistScore(DomainModel):
    """Результат скоринга одного кандидата при классификации."""

    code: ChecklistCode

    score: float = Field(ge=0)

    matched_hints: tuple[str, ...] = Field(
        default_factory=tuple,
    )


class ChecklistSuggestion(DomainModel):
    """Предложение сервиса, которое требует подтверждения пользователя."""

    recommended_code: ChecklistCode

    confidence: float = Field(
        ge=0,
        le=1,
    )

    ranking: tuple[ChecklistScore, ...] = Field(
        min_length=1,
    )

    requires_confirmation: bool = True


class ConfirmedChecklist(DomainModel):
    """Явно подтверждённый пользователем выбор чек-листа."""

    code: ChecklistCode

    title: str = Field(min_length=1)


class ChecklistSelectionResult(DomainModel):
    """Полный результат сценария автоматического выбора чек-листа.

    Помимо самой рекомендации содержит диагностическую информацию,
    необходимую для тестов, логирования и последующего анализа
    поведения классификатора.
    """

    suggestion: ChecklistSuggestion

    source: ClassificationSource

    fallback_reason: VlmFallbackReason | None = None

    vision_pages: tuple[int, ...] = Field(
        default_factory=tuple,
    )

    @model_validator(mode="after")
    def validate_fallback_metadata(
        self,
    ) -> "ChecklistSelectionResult":
        """Проверить согласованность source и VLM-метаданных."""
        if self.source == ClassificationSource.NATIVE_TEXT:
            if self.fallback_reason is not None:
                raise ValueError(
                    "Native-text result cannot contain "
                    "VLM fallback reason"
                )

            if self.vision_pages:
                raise ValueError(
                    "Native-text result cannot contain "
                    "VLM page numbers"
                )

        if self.source == ClassificationSource.NATIVE_TEXT_AND_VLM:
            if self.fallback_reason is None:
                raise ValueError(
                    "VLM result must contain fallback reason"
                )

            if not self.vision_pages:
                raise ValueError(
                    "VLM result must contain analyzed page numbers"
                )

        return self
