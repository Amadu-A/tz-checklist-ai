# app/application/services/checklist_classifier.py

import re
from difflib import SequenceMatcher

from app.domain.checklists import (
    ChecklistCatalog,
    ChecklistScore,
    ChecklistSuggestion,
)


class ChecklistClassifier:
    """Детерминированно ранжирует чек-листы по содержимому документа.

    Классификатор работает как с native text PDF, так и с текстовым
    evidence, полученным через VLM fallback.

    Поиск не основан на точном сравнении целой строки. Русские
    технические документы содержат одни и те же термины в разных
    падежах, поэтому фразы сравниваются как последовательности
    нормализованных слов.

    Например:

        "насосная установка пожаротушения"
        "насосную установку пожаротушения"

    должны рассматриваться как один классификационный признак.

    Алгоритм остаётся детерминированным и объяснимым:
    для каждого результата сохраняются реально совпавшие hints.

    Результат классификатора является только рекомендацией.
    Окончательный чек-лист всегда подтверждает пользователь.
    """

    _WORD_RE = re.compile(
        r"[0-9a-zа-я]+",
        flags=re.IGNORECASE,
    )

    # Лёгкая нормализация наиболее распространённых русских
    # словоизменительных окончаний.
    #
    # Это намеренно не полноценный лингвистический stemmer:
    # для пяти фиксированных технических классов нам достаточно
    # устойчиво сопоставлять формы одного термина, не добавляя
    # тяжёлую NLP-зависимость в проект.
    _RUSSIAN_ENDINGS = tuple(
        sorted(
            {
                "иями",
                "ями",
                "ами",
                "ого",
                "его",
                "ому",
                "ему",
                "ыми",
                "ими",
                "ая",
                "яя",
                "ую",
                "юю",
                "ое",
                "ее",
                "ие",
                "ые",
                "ий",
                "ый",
                "ой",
                "ей",
                "ым",
                "им",
                "ам",
                "ям",
                "ах",
                "ях",
                "ов",
                "ев",
                "ом",
                "ем",
                "а",
                "я",
                "ы",
                "и",
                "у",
                "ю",
                "е",
                "о",
            },
            key=len,
            reverse=True,
        )
    )

    def __init__(
        self,
        catalog: ChecklistCatalog,
    ) -> None:
        """Сохранить неизменяемый каталог классификационных признаков."""
        self._catalog = catalog

    def classify(
        self,
        document_text: str,
    ) -> ChecklistSuggestion:
        """Построить ranking пяти чек-листов по содержимому документа."""
        document_tokens = self._tokenize(
            document_text
        )

        scores: list[
            ChecklistScore
        ] = []

        for checklist in self._catalog.checklists:
            raw_score = 0.0

            matched: list[
                str
            ] = []

            for hint in checklist.classifier_hints:
                hint_tokens = self._tokenize(
                    hint.text
                )

                occurrences = (
                    self._count_hint_occurrences(
                        document_tokens=(
                            document_tokens
                        ),
                        hint_tokens=(
                            hint_tokens
                        ),
                    )
                )

                if occurrences == 0:
                    continue

                # Частое повторение одного технического термина
                # не должно бесконечно увеличивать вероятность.
                raw_score += (
                    hint.weight
                    * min(
                        occurrences,
                        3,
                    )
                )

                matched.append(
                    hint.text
                )

            scores.append(
                ChecklistScore(
                    code=checklist.code,
                    score=raw_score,
                    matched_hints=tuple(
                        matched
                    ),
                )
            )

        ranking = tuple(
            sorted(
                scores,
                key=lambda item: (
                    item.score
                ),
                reverse=True,
            )
        )

        top = ranking[0]

        positive_total = sum(
            item.score
            for item in ranking
        )

        confidence = (
            top.score
            / positive_total
            if positive_total > 0
            else 0.0
        )

        # Если ни один реальный признак не найден,
        # нельзя выбирать первый элемент каталога просто
        # из-за порядка сортировки.
        recommended_code = (
            top.code
            if top.score > 0
            else None
        )

        return ChecklistSuggestion(
            recommended_code=(
                recommended_code
            ),
            confidence=round(
                confidence,
                4,
            ),
            ranking=ranking,
        )

    @classmethod
    def _count_hint_occurrences(
        cls,
        *,
        document_tokens: tuple[
            str,
            ...,
        ],
        hint_tokens: tuple[
            str,
            ...,
        ],
    ) -> int:
        """Посчитать вхождения hint с учётом русских словоформ.

        Слова должны идти в том же порядке, что и в исходном hint.
        Благодаря этому схожие слова в разных частях страницы
        не превращаются в ложное совпадение целой фразы.
        """
        if (
            not hint_tokens
            or len(hint_tokens)
            > len(document_tokens)
        ):
            return 0

        window_size = len(
            hint_tokens
        )

        occurrences = 0

        for start in range(
            len(document_tokens)
            - window_size
            + 1
        ):
            document_window = (
                document_tokens[
                    start:
                    start + window_size
                ]
            )

            if all(
                cls._tokens_match(
                    hint_token,
                    document_token,
                )
                for (
                    hint_token,
                    document_token,
                ) in zip(
                    hint_tokens,
                    document_window,
                    strict=True,
                )
            ):
                occurrences += 1

        return occurrences

    @classmethod
    def _tokenize(
        cls,
        value: str,
    ) -> tuple[
        str,
        ...,
    ]:
        """Разбить текст на слова и выполнить лёгкую нормализацию."""
        normalized = (
            cls._normalize(
                value
            )
        )

        return tuple(
            cls._light_stem(
                token
            )
            for token
            in cls._WORD_RE.findall(
                normalized
            )
        )

    @classmethod
    def _light_stem(
        cls,
        token: str,
    ) -> str:
        """Удалить типичное русское словоизменительное окончание.

        Очень короткие слова, аббревиатуры и латинские identifiers
        оставляются без изменений.
        """
        if (
            len(token) < 5
            or re.fullmatch(
                r"[а-я]+",
                token,
            )
            is None
        ):
            return token

        for ending in cls._RUSSIAN_ENDINGS:
            if (
                token.endswith(
                    ending
                )
                and len(token)
                - len(ending)
                >= 4
            ):
                return token[
                    :-len(ending)
                ]

        return token

    @staticmethod
    def _tokens_match(
        first: str,
        second: str,
    ) -> bool:
        """Сравнить два уже нормализованных технических термина.

        Сначала используется точное совпадение stem.

        Для коротких нерегулярных словоформ вроде:

            узел / узла

        применяется консервативное fuzzy-сравнение.
        """
        if first == second:
            return True

        if min(
            len(first),
            len(second),
        ) < 4:
            return False

        # Разные начала слов почти наверняка означают
        # разные технические термины.
        if (
            first[:2]
            != second[:2]
        ):
            return False

        similarity = (
            SequenceMatcher(
                None,
                first,
                second,
            ).ratio()
        )

        return similarity >= 0.75

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """Нормализовать регистр, букву ё и последовательности пробелов."""
        value = (
            value
            .casefold()
            .replace(
                "ё",
                "е",
            )
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()
