# app/application/services/document_chunker.py

from app.domain.documents import DocumentTextContext
from app.domain.retrieval import DocumentChunk


class DocumentChunker:
    """Разбивает native text на небольшие page-aware fragments.

    Chunk никогда не пересекает границу PDF-страницы.

    Это важно, потому что дальше мы должны иметь возможность:
    - показать evidence page;
    - при необходимости отрендерить именно эту страницу для VLM;
    - указать source_pages для найденного ответа.

    Используется overlap, чтобы значение на границе двух chunks
    не потерялось при retrieval.
    """

    def __init__(
        self,
        *,
        max_chars: int,
        overlap_chars: int,
    ) -> None:
        if max_chars <= 0:
            raise ValueError(
                "max_chars must be positive"
            )

        if overlap_chars < 0:
            raise ValueError(
                "overlap_chars cannot be negative"
            )

        if overlap_chars >= max_chars:
            raise ValueError(
                "overlap_chars must be smaller than max_chars"
            )

        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def chunk(
        self,
        context: DocumentTextContext,
    ) -> tuple[DocumentChunk, ...]:
        """Создать chunks для всех страниц, имеющих native text."""
        result: list[DocumentChunk] = []

        for page in context.pages:
            text = self._normalize_page_text(
                page.text
            )

            if not text:
                continue

            page_chunks = self._split_page(
                text
            )

            for chunk_index, chunk_text in enumerate(
                page_chunks,
                start=1,
            ):
                result.append(
                    DocumentChunk(
                        chunk_id=(
                            f"p{page.page_number}"
                            f"-c{chunk_index}"
                        ),
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                    )
                )

        return tuple(result)

    def _split_page(
        self,
        text: str,
    ) -> tuple[str, ...]:
        """Разбить одну страницу по словам с character limit."""
        words = text.split()

        if not words:
            return ()

        chunks: list[str] = []
        start = 0

        while start < len(words):
            end = start
            current_chars = 0

            while end < len(words):
                word = words[end]

                additional = (
                    len(word)
                    + (
                        1
                        if end > start
                        else 0
                    )
                )

                if (
                    end > start
                    and current_chars + additional > self._max_chars
                ):
                    break

                current_chars += additional
                end += 1

            # Даже аномально длинное одиночное слово
            # должно позволить алгоритму двигаться дальше.
            if end == start:
                end = start + 1

            chunks.append(
                " ".join(
                    words[start:end]
                )
            )

            if end >= len(words):
                break

            overlap_start = end
            overlap_size = 0

            while overlap_start > start:
                previous_word = (
                    words[
                        overlap_start - 1
                    ]
                )

                additional = (
                    len(previous_word)
                    + (
                        1
                        if overlap_size > 0
                        else 0
                    )
                )

                if (
                    overlap_size + additional
                    > self._overlap_chars
                ):
                    break

                overlap_size += additional
                overlap_start -= 1

            # Гарантируем progress даже при очень большом overlap.
            start = (
                overlap_start
                if overlap_start > start
                else end
            )

        return tuple(chunks)

    @staticmethod
    def _normalize_page_text(
        text: str,
    ) -> str:
        """Убрать PDF-артефакты пробелов, не меняя содержание."""
        lines = (
            text
            .replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
            .split("\n")
        )

        return "\n".join(
            line.strip()
            for line in lines
            if line.strip()
        )
    