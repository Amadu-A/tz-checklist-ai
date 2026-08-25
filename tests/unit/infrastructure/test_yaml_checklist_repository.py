# tests/unit/infrastructure/test_yaml_checklist_repository.py

from pathlib import Path

from app.domain.enums import ChecklistCode
from app.infrastructure.checklists.yaml_checklist_repository import (
    YamlChecklistRepository,
)


RESOURCES = (
    Path(__file__).parents[3]
    / "resources"
    / "checklists"
)


def test_repository_loads_all_five_checklists() -> None:
    """В production должны существовать ровно пять типов."""
    repository = (
        YamlChecklistRepository(
            RESOURCES
        )
    )

    definitions = (
        repository.list()
    )

    assert {
        item.code
        for item
        in definitions
    } == set(
        ChecklistCode
    )


def test_question_counts_match_immutable_sources() -> None:
    """Количество вопросов должно совпадать с XLSX-источниками."""
    repository = (
        YamlChecklistRepository(
            RESOURCES
        )
    )

    assert len(
        repository.get(
            ChecklistCode.UUTE
        ).questions
    ) == 41

    assert len(
        repository.get(
            ChecklistCode.ITP
        ).questions
    ) == 75

    assert len(
        repository.get(
            ChecklistCode.MKBI
        ).questions
    ) == 82

    assert len(
        repository.get(
            ChecklistCode.SPD
        ).questions
    ) == 25

    assert len(
        repository.get(
            ChecklistCode.AUPT
        ).questions
    ) == 30


def test_itp_preserves_two_source_sheets() -> None:
    """ИТП обязан сохранить оба листа исходного Excel."""
    repository = (
        YamlChecklistRepository(
            RESOURCES
        )
    )

    checklist = repository.get(
        ChecklistCode.ITP
    )

    assert len(
        checklist.sheets
    ) == 2

    assert len(
        checklist
        .sheets[1]
        .sections[0]
        .questions
    ) == 7

    assert len(
        checklist
        .sheets[1]
        .sections[1]
        .questions
    ) == 11


def test_mkbi_keeps_known_corrupted_source_question_without_silent_fix() -> None:
    """Ошибка оригинального XLSX должна быть задокументирована."""
    repository = (
        YamlChecklistRepository(
            RESOURCES
        )
    )

    checklist = repository.get(
        ChecklistCode.MKBI
    )

    question = next(
        item
        for item
        in checklist.questions
        if item.id == "main-64"
    )

    assert (
        question.source_issue
        is not None
    )

    assert (
        "+C70+C72"
        in question.text
    )
