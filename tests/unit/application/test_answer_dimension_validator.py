# tests/unit/application/test_answer_dimension_validator.py

from app.application.services.answer_dimension_validator import (
    AnswerDimensionValidator,
)


def test_pressure_rejects_voltage_and_frequency() -> None:
    """400 В / 50 Гц нельзя использовать как давление."""
    validator = AnswerDimensionValidator()

    assert (
        validator.is_valid(
            question=(
                "Какое рабочее давление СПД "
                "(Pmax) указано в МПа или бар?"
            ),
            answer="3~400В 50Гц",
        )
        is False
    )


def test_pressure_accepts_pressure_unit() -> None:
    """кгс/см² является допустимой единицей давления."""
    validator = AnswerDimensionValidator()

    assert validator.is_valid(
        question=(
            "Какое давление теплоносителя указано?"
        ),
        answer="5,8 кгс/см²",
    )


def test_temperature_accepts_celsius() -> None:
    """Температура в °С должна пройти."""
    validator = AnswerDimensionValidator()

    assert validator.is_valid(
        question=(
            "Какая температура теплоносителя указана?"
        ),
        answer="95 °С; 70 °С",
    )


def test_numeric_flow_without_unit_is_allowed() -> None:
    """Табличное число допустимо, если вопрос уже задаёт расход."""
    validator = AnswerDimensionValidator()

    assert validator.is_valid(
        question=(
            "Какой максимальный расчетный расход "
            "указан в м³/ч?"
        ),
        answer="857,66",
    )


def test_diameter_rejects_paint_description() -> None:
    """Описание окраски не является диаметром."""
    validator = AnswerDimensionValidator()

    assert (
        validator.is_valid(
            question=(
                "Какой диаметр подающего "
                "трубопровода указан?"
            ),
            answer=(
                "Подающий трубопровод окрашен "
                "эмалью ПФ-115 красного цвета"
            ),
        )
        is False
    )


def test_non_dimensional_question_is_unchanged() -> None:
    """Материал/тип/организация не должны фильтроваться."""
    validator = AnswerDimensionValidator()

    assert validator.is_valid(
        question=(
            "Какой материал проточной части насосов указан?"
        ),
        answer="нержавеющая сталь",
    )
    