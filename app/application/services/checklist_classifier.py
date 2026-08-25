# app/application/services/checklist_classifier.py

import re

from app.domain.checklists import (
    ChecklistCatalog,
    ChecklistScore,
    ChecklistSuggestion,
)


class ChecklistClassifier:
    """Ранжирует пять чек-листов по содержимому, извлечённому VLM.

    VLM отвечает за чтение страницы как изображения.
    Этот класс выполняет объяснимое ранжирование по фиксированному
    каталогу признаков.

    Результат никогда не считается окончательным выбором:
    требуется подтверждение пользователя.
    """

    def __init__(
        self,
        catalog: ChecklistCatalog,
    ) -> None:
        self._catalog = catalog

    def classify(
        self,
        document_text: str,
    ) -> ChecklistSuggestion:
        """Вернуть ранжированный список чек-листов."""
        normalized = self._normalize(
            document_text
        )

        scores: list[ChecklistScore] = []

        for checklist in self._catalog.checklists:
            raw_score = 0.0
            matched: list[str] = []

            for hint in checklist.classifier_hints:
                hint_text = self._normalize(
                    hint.text
                )

                occurrences = normalized.count(
                    hint_text
                )

                if occurrences == 0:
                    continue

                # Частое повторение одного слова не должно
                # бесконечно увеличивать вероятность.
                raw_score += (
                    hint.weight
                    * min(occurrences, 3)
                )

                matched.append(
                    hint.text
                )

            scores.append(
                ChecklistScore(
                    code=checklist.code,
                    score=raw_score,
                    matched_hints=tuple(matched),
                )
            )

        ranking = tuple(
            sorted(
                scores,
                key=lambda item: item.score,
                reverse=True,
            )
        )

        top = ranking[0]

        positive_total = sum(
            item.score
            for item in ranking
        )

        confidence = (
            top.score / positive_total
            if positive_total > 0
            else 0.0
        )

        return ChecklistSuggestion(
            recommended_code=top.code,
            confidence=round(
                confidence,
                4,
            ),
            ranking=ranking,
        )

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """Нормализовать регистр и пробелы без изменения смысла."""
        value = (
            value
            .casefold()
            .replace("ё", "е")
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()
    