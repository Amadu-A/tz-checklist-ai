# tests/unit/test_retrieval_config.py

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_retrieval_configuration_is_safe() -> None:
    """Проверить production defaults retrieval pipeline."""
    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.retrieval_chunk_max_chars
        == 1800
    )

    assert (
        settings.retrieval_chunk_overlap_chars
        == 300
    )

    assert (
        settings.retrieval_top_k
        == 6
    )

    assert (
        settings.retrieval_embedding_batch_size
        == 16
    )


def test_overlap_must_be_smaller_than_chunk() -> None:
    """Pydantic должен запрещать конфигурацию без progress."""
    with pytest.raises(
        ValidationError
    ):
        Settings(
            _env_file=None,
            retrieval_chunk_max_chars=500,
            retrieval_chunk_overlap_chars=500,
        )


def test_both_retrieval_weights_cannot_be_zero() -> None:
    """Нельзя случайно отключить оба retrieval-механизма."""
    with pytest.raises(
        ValidationError
    ):
        Settings(
            _env_file=None,
            retrieval_semantic_weight=0,
            retrieval_lexical_weight=0,
        )
