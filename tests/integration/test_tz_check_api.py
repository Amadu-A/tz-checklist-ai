# tests/integration/test_tz_check_api.py

from uuid import uuid4

import httpx

from app.api.dependencies import (
    get_tz_check_workflow_service,
)
from app.domain.checklists import (
    ChecklistScore,
    ChecklistSelectionResult,
    ChecklistSuggestion,
    ConfirmedChecklist,
)
from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
    JobStatus,
)
from app.domain.workflow import (
    WorkflowConfirmationResult,
    WorkflowSelectionResult,
    WorkflowStatusResult,
)
from app.main import app

REQUEST_ID = uuid4()


class FakeWorkflowService:
    """Стаб всего application workflow для проверки HTTP contract."""

    async def select(
        self,
        pdf_bytes: bytes,
    ) -> WorkflowSelectionResult:
        assert pdf_bytes.startswith(
            b"%PDF-"
        )

        return WorkflowSelectionResult(
            request_id=REQUEST_ID,
            selection=(
                ChecklistSelectionResult(
                    suggestion=(
                        ChecklistSuggestion(
                            recommended_code=(
                                ChecklistCode.UUTE
                            ),
                            confidence=0.91,
                            ranking=(
                                ChecklistScore(
                                    code=(
                                        ChecklistCode
                                        .UUTE
                                    ),
                                    score=5,
                                    matched_hints=(
                                        "тепловычислитель",
                                    ),
                                ),
                                ChecklistScore(
                                    code=(
                                        ChecklistCode
                                        .ITP
                                    ),
                                    score=1,
                                ),
                            ),
                        )
                    ),
                    source=(
                        ClassificationSource
                        .NATIVE_TEXT
                    ),
                )
            ),
        )

    def confirm(
        self,
        *,
        request_id,
        checklist_code,
    ) -> WorkflowConfirmationResult:
        assert (
            request_id
            == REQUEST_ID
        )

        return WorkflowConfirmationResult(
            request_id=request_id,
            checklist=ConfirmedChecklist(
                code=checklist_code,
                title="УУТЭ",
            ),
            status=JobStatus.QUEUED,
        )

    def status(
        self,
        request_id,
    ) -> WorkflowStatusResult:
        return WorkflowStatusResult(
            request_id=request_id,
            status=JobStatus.COMPLETED,
            checklist_code=ChecklistCode.UUTE,
            progress_percent=100,
            result_ready=True,
        )

    def result(
        self,
        request_id,
    ) -> bytes:
        assert (
            request_id
            == REQUEST_ID
        )

        return b"%PDF-test-result"


async def _post(
    *,
    data: dict[str, str],
    files=None,
) -> httpx.Response:
    """Вызвать endpoint напрямую через ASGI."""
    transport = httpx.ASGITransport(
        app=app
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.post(
            "/api/v1/tz-check",
            data=data,
            files=files,
        )


async def test_single_endpoint_supports_full_state_machine() -> None:
    """Все четыре действия должны работать через один URL."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
        select_response = await _post(
            data={
                "action": "select",
            },
            files={
                "file": (
                    "tz.pdf",
                    b"%PDF-1.4 test",
                    "application/pdf",
                ),
            },
        )

        assert (
            select_response.status_code
            == 200
        )

        select_payload = (
            select_response.json()
        )

        assert (
            select_payload[
                "request_id"
            ]
            == str(
                REQUEST_ID
            )
        )

        assert (
            select_payload[
                "recommended_checklist"
            ]
            == "UUTE"
        )

        assert (
            select_payload["status"]
            == "awaiting_confirmation"
        )

        confirm_response = await _post(
            data={
                "action": "confirm",
                "request_id": str(
                    REQUEST_ID
                ),
                "checklist_code": "UUTE",
            }
        )

        assert (
            confirm_response.status_code
            == 200
        )

        assert (
            confirm_response.json()[
                "status"
            ]
            == "queued"
        )

        status_response = await _post(
            data={
                "action": "status",
                "request_id": str(
                    REQUEST_ID
                ),
            }
        )

        assert (
            status_response.status_code
            == 200
        )

        assert (
            status_response.json()[
                "progress_percent"
            ]
            == 100
        )

        assert (
            status_response.json()[
                "result_ready"
            ]
            is True
        )

        result_response = await _post(
            data={
                "action": "result",
                "request_id": str(
                    REQUEST_ID
                ),
            }
        )

        assert (
            result_response.status_code
            == 200
        )

        assert (
            result_response.headers[
                "content-type"
            ]
            == "application/pdf"
        )

        assert (
            result_response.headers[
                "cache-control"
            ]
            == "no-store"
        )

        assert (
            result_response.content
            == b"%PDF-test-result"
        )

    finally:
        app.dependency_overrides.clear()


async def test_select_requires_file() -> None:
    """action=select без PDF должен вернуть понятный 400."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
        response = await _post(
            data={
                "action": "select",
            }
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 400
    )

    assert (
        response.json()[
            "detail"
        ]
        == (
            "file is required "
            "for action=select"
        )
    )
