# tests/unit/application/test_checklist_classifier.py

import pytest

from app.application.services.checklist_classifier import (
    ChecklistClassifier,
)
from app.domain.checklists import (
    ChecklistCatalog,
    ChecklistCatalogEntry,
    ClassifierHint,
)
from app.domain.enums import ChecklistCode


@pytest.fixture
def classifier() -> ChecklistClassifier:
    """Создать изолированный каталог для unit-тестов классификатора.

    Тестовый каталог намеренно содержит все пять поддерживаемых
    типов чек-листов, но только по одному сильному признаку на тип.
    Это позволяет проверять непосредственно алгоритм классификации,
    не связывая unit-тест с production YAML-файлами.
    """
    catalog = ChecklistCatalog(
        checklists=(
            ChecklistCatalogEntry(
                code=ChecklistCode.UUTE,
                title="УУТЭ",
                description=(
                    "Узел учета тепловой энергии"
                ),
                classifier_hints=(
                    ClassifierHint(
                        text=(
                            "коммерческий узел "
                            "учета тепловой энергии"
                        ),
                        weight=12,
                    ),
                ),
            ),
            ChecklistCatalogEntry(
                code=ChecklistCode.ITP,
                title="ИТП",
                description=(
                    "Индивидуальный тепловой пункт"
                ),
                classifier_hints=(
                    ClassifierHint(
                        text=(
                            "индивидуальный "
                            "тепловой пункт"
                        ),
                        weight=12,
                    ),
                ),
            ),
            ChecklistCatalogEntry(
                code=ChecklistCode.MKBI,
                title="МКБИ",
                description=(
                    "Блочно-модульная котельная"
                ),
                classifier_hints=(
                    ClassifierHint(
                        text=(
                            "блочно-модульная "
                            "котельная"
                        ),
                        weight=14,
                    ),
                ),
            ),
            ChecklistCatalogEntry(
                code=ChecklistCode.SPD,
                title="СПД",
                description=(
                    "Насосная станция"
                ),
                classifier_hints=(
                    ClassifierHint(
                        text=(
                            "насосная станция "
                            "второго подъема"
                        ),
                        weight=12,
                    ),
                ),
            ),
            ChecklistCatalogEntry(
                code=ChecklistCode.AUPT,
                title="АУПТ",
                description=(
                    "Установка пожаротушения"
                ),
                classifier_hints=(
                    ClassifierHint(
                        text=(
                            "насосная установка "
                            "пожаротушения"
                        ),
                        weight=14,
                    ),
                ),
            ),
        )
    )

    return ChecklistClassifier(
        catalog
    )


@pytest.mark.parametrize(
    (
        "document_text",
        "expected_code",
    ),
    [
        (
            (
                "Проект коммерческого узла "
                "учета тепловой энергии."
            ),
            ChecklistCode.UUTE,
        ),
        (
            (
                "Оборудование индивидуального "
                "теплового пункта."
            ),
            ChecklistCode.ITP,
        ),
        (
            (
                "Оборудование блочно-модульной "
                "котельной."
            ),
            ChecklistCode.MKBI,
        ),
        (
            (
                "Автоматизация насосной станции "
                "второго подъема."
            ),
            ChecklistCode.SPD,
        ),
        (
            (
                "Опросный лист на насосную "
                "установку пожаротушения."
            ),
            ChecklistCode.AUPT,
        ),
    ],
)
def test_classifier_matches_russian_inflected_forms(
    classifier: ChecklistClassifier,
    document_text: str,
    expected_code: ChecklistCode,
) -> None:
    """Русские падежи не должны ломать классификацию.

    Production-каталог хранит канонические формулировки признаков,
    однако в реальном ТЗ эти же термины встречаются в различных
    грамматических формах.

    Проверяем, что классификатор устойчив к таким изменениям.
    """
    result = classifier.classify(
        document_text
    )

    assert (
        result.recommended_code
        == expected_code
    )

    assert (
        result.ranking[0].score
        > 0
    )

    assert (
        result.ranking[0].matched_hints
    )


def test_classifier_does_not_default_to_first_checklist_without_evidence(
    classifier: ChecklistClassifier,
) -> None:
    """Неизвестный документ не должен автоматически становиться УУТЭ.

    Если ни один классификационный признак не найден, правильное
    поведение — вернуть отсутствие рекомендации, а не первый элемент
    каталога.

    В дальнейшем пользователь сможет самостоятельно выбрать
    подходящий чек-лист.
    """
    result = classifier.classify(
        "Архитектурные решения фасада. "
        "Отделка стен и оконные проемы."
    )

    assert (
        result.recommended_code
        is None
    )

    assert (
        result.confidence
        == 0.0
    )

    assert all(
        item.score == 0
        for item in result.ranking
    )
