# app/infrastructure/reporting/reportlab_checklist_renderer.py

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from app.domain.answers import ChecklistAnalysisResult
from app.domain.checklists import ChecklistDefinition


class ReportLabChecklistRenderer:
    """Формирует итоговый PDF строго с тремя колонками.

    Колонки:

        № | Вопрос | Ответ

    Внутренние статусы, confidence и source pages пользователю
    не выводятся.

    NOT_FOUND и LOW_CONFIDENCE дают пустую колонку ответа.
    """

    REGULAR_FONT_NAME = "TZChecklistDejaVu"

    BOLD_FONT_NAME = "TZChecklistDejaVuBold"

    def __init__(
        self,
        *,
        regular_font_path: Path = Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        bold_font_path: Path = Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ),
    ) -> None:
        if not regular_font_path.is_file():
            raise FileNotFoundError(
                regular_font_path
            )

        if not bold_font_path.is_file():
            raise FileNotFoundError(
                bold_font_path
            )

        pdfmetrics.registerFont(
            TTFont(
                self.REGULAR_FONT_NAME,
                str(regular_font_path),
            )
        )

        pdfmetrics.registerFont(
            TTFont(
                self.BOLD_FONT_NAME,
                str(bold_font_path),
            )
        )

    def render(
        self,
        *,
        checklist: ChecklistDefinition,
        analysis: ChecklistAnalysisResult,
    ) -> bytes:
        """Сформировать PDF полностью в RAM."""
        if (
            checklist.code
            != analysis.checklist_code
        ):
            raise ValueError(
                "Checklist code does not match analysis result"
            )

        answer_map = {
            answer.question_id: answer
            for answer in analysis.answers
        }

        expected_ids = {
            question.id
            for question in checklist.questions
        }

        if set(answer_map) != expected_ids:
            raise ValueError(
                "Analysis result does not contain "
                "exactly one answer for every checklist question"
            )

        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=checklist.title,
        )

        normal_style = ParagraphStyle(
            name="ChecklistNormal",
            fontName=self.REGULAR_FONT_NAME,
            fontSize=8,
            leading=10,
        )

        header_style = ParagraphStyle(
            name="ChecklistHeader",
            parent=normal_style,
            fontName=self.BOLD_FONT_NAME,
            alignment=TA_CENTER,
        )

        section_style = ParagraphStyle(
            name="ChecklistSection",
            parent=normal_style,
            fontName=self.BOLD_FONT_NAME,
        )

        title_style = ParagraphStyle(
            name="ChecklistTitle",
            parent=normal_style,
            fontName=self.BOLD_FONT_NAME,
            fontSize=12,
            leading=15,
            alignment=TA_CENTER,
        )

        rows: list[list[object]] = [
            [
                Paragraph(
                    "№",
                    header_style,
                ),
                Paragraph(
                    "Вопрос",
                    header_style,
                ),
                Paragraph(
                    "Ответ",
                    header_style,
                ),
            ]
        ]

        span_rows: list[int] = []

        for sheet in checklist.sheets:
            span_rows.append(
                len(rows)
            )

            rows.append(
                [
                    Paragraph(
                        sheet.title,
                        section_style,
                    ),
                    "",
                    "",
                ]
            )

            for section in sheet.sections:
                if (
                    section.title.strip()
                    and section.title.strip()
                    != sheet.title.strip()
                ):
                    span_rows.append(
                        len(rows)
                    )

                    rows.append(
                        [
                            Paragraph(
                                section.title,
                                section_style,
                            ),
                            "",
                            "",
                        ]
                    )

                for question in section.questions:
                    answer = answer_map[
                        question.id
                    ]

                    rows.append(
                        [
                            Paragraph(
                                question.source_number,
                                normal_style,
                            ),
                            Paragraph(
                                question.text,
                                normal_style,
                            ),
                            Paragraph(
                                answer.output_answer,
                                normal_style,
                            ),
                        ]
                    )

        table = LongTable(
            rows,
            colWidths=[
                16 * mm,
                112 * mm,
                42 * mm,
            ],
            repeatRows=1,
            hAlign="CENTER",
        )

        commands: list[tuple[object, ...]] = [
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.black,
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey,
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                3,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                3,
            ),
        ]

        for row_number in span_rows:
            commands.extend(
                [
                    (
                        "SPAN",
                        (0, row_number),
                        (-1, row_number),
                    ),
                    (
                        "BACKGROUND",
                        (0, row_number),
                        (-1, row_number),
                        colors.whitesmoke,
                    ),
                ]
            )

        table.setStyle(
            TableStyle(
                commands
            )
        )

        story = [
            Paragraph(
                checklist.title,
                title_style,
            ),
            Spacer(
                1,
                6 * mm,
            ),
            table,
        ]

        document.build(
            story
        )

        return buffer.getvalue()
    