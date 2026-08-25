# tests/unit/application/test_confirm_checklist.py

from pathlib import Path

from app.application.use_cases.confirm_checklist import (
    ConfirmChecklistUseCase,
)
from app.domain.enums import ChecklistCode
from app.infrastructure.checklists.yaml_checklist_repository import (
    YamlChecklistRepository,
)


RESOURCES = (
    Path(__file__).parents[3]
    / "resources"
    / "checklists"
)


def test_user_can_confirm_any_existing_checklist_not_only_recommended_one() -> None:
    """Пользователь должен иметь право заменить рекомендацию AI."""
    repository = (
        YamlChecklistRepository(
            RESOURCES
        )
    )

    use_case = (
        ConfirmChecklistUseCase(
            repository
        )
    )

    result = use_case.execute(
        ChecklistCode.SPD
    )

    assert (
        result.code
        == ChecklistCode.SPD
    )

    assert (
        result.title
        == "СПД"
    )
    