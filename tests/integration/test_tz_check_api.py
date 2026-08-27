# tests/integration/test_tz_check_api.py

import json
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
    ChecklistTag,
    ClassificationSource,
    JobStatus,
)
from app.domain.workflow import (
    WorkflowConfirmationResult,
    WorkflowSelectionResult,
    WorkflowStatusResult,
    WorkflowTaggedSubmissionResult,
)
from app.main import app

REQUEST_ID = uuid4()


class FakeWorkflowService:
    """Стаб workflow для проверки HTTP-контракта."""

    async def select(
        self,
        pdf_bytes: bytes,
        *,
        source_filename: str = "document.pdf",
        checklist_tag: ChecklistTag | None = None,
    ):
        assert pdf_bytes.startswith(
            b"%PDF-"
        )

        assert (
            source_filename
            == "tz.pdf"
        )

        if checklist_tag is not None:
            return WorkflowTaggedSubmissionResult(
                request_id=REQUEST_ID,
                checklist=ConfirmedChecklist(
                    code=checklist_tag.code,
                    title=checklist_tag.value,
                ),
                checklist_tag=checklist_tag,
            )

        return WorkflowSelectionResult(
            request_id=REQUEST_ID,
            selection=ChecklistSelectionResult(
                suggestion=ChecklistSuggestion(
                    recommended_code=(
                        ChecklistCode.UUTE
                    ),
                    confidence=0.91,
                    ranking=(
                        ChecklistScore(
                            code=ChecklistCode.UUTE,
                            score=5,
                            matched_hints=(
                                "тепловычислитель",
                            ),
                        ),
                        ChecklistScore(
                            code=ChecklistCode.ITP,
                            score=1,
                        ),
                    ),
                ),
                source=(
                    ClassificationSource
                    .NATIVE_TEXT
                ),
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
                title=(
                    ChecklistTag
                    .from_code(
                        checklist_code
                    )
                    .value
                ),
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

        return json.dumps(
            {
                "metadata": {
                    "request_id": str(
                        request_id
                    ),
                    "checklist_type": (
                        "Узел учета тепловой энергии"
                    ),
                    "checklist_tag": "УУТЭ",
                    "checklist_code": "UUTE",
                    "source_filename": "tz.pdf",
                    "processing_seconds": 12.3,
                    "search_seconds": 10.1,
                    "completed_at": (
                        "2026-08-27T10:00:00Z"
                    ),
                    "question_count": 1,
                },
                "questions": [
                    {
                        "number": "1",
                        "question": "Вопрос?",
                        "answer": "Ответ",
                    }
                ],
            },
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )


async def _post(
    *,
    data: dict[str, str],
    files=None,
) -> httpx.Response:
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


async def test_without_tag_uses_auto_detection_and_confirmation() -> None:
    """Без tag остаётся старый state machine."""
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

        payload = select_response.json()

        assert (
            payload["status"]
            == "awaiting_confirmation"
        )

        assert (
            payload["selection_mode"]
            == "automatic"
        )

        assert (
            payload["recommended_checklist"]
            == "UUTE"
        )

        assert (
            payload["recommended_tag"]
            == "УУТЭ"
        )

        assert (
            payload["requires_confirmation"]
            is True
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

    finally:
        app.dependency_overrides.clear()


async def test_with_tag_skips_classification_and_confirmation() -> None:
    """file + tag сразу возвращает QUEUED."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
        response = await _post(
            data={
                "action": "select",
                "checklist_tag": "Мкби",
            },
            files={
                "file": (
                    "tz.pdf",
                    b"%PDF-1.4 test",
                    "application/pdf",
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["status"]
        == "queued"
    )

    assert (
        payload["selection_mode"]
        == "provided_tag"
    )

    assert (
        payload["checklist_code"]
        == "MKBI"
    )

    assert (
        payload["checklist_tag"]
        == "МКБИ"
    )

    assert (
        payload["requires_confirmation"]
        is False
    )


async def test_auto_flow_can_be_confirmed_by_public_tag() -> None:
    """После auto-detection клиент может подтвердить русским tag."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
        response = await _post(
            data={
                "action": "confirm",
                "request_id": str(
                    REQUEST_ID
                ),
                "checklist_tag": "Уутэ",
            }
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["checklist_code"]
        == "UUTE"
    )

    assert (
        payload["checklist_tag"]
        == "УУТЭ"
    )


async def test_conflicting_code_and_tag_are_rejected() -> None:
    """Code/tag не могут указывать на разные checklists."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
        response = await _post(
            data={
                "action": "confirm",
                "request_id": str(
                    REQUEST_ID
                ),
                "checklist_code": "UUTE",
                "checklist_tag": "СПД",
            }
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 400
    )


async def test_invalid_tag_is_rejected_by_api_validation() -> None:
    """Неизвестный tag не должен запускать job."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
        response = await _post(
            data={
                "action": "select",
                "checklist_tag": "UNKNOWN",
            },
            files={
                "file": (
                    "tz.pdf",
                    b"%PDF-1.4 test",
                    "application/pdf",
                ),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 422
    )


async def test_status_and_result_return_json() -> None:
    """Completed job должен вернуть application/json."""
    app.dependency_overrides[
        get_tz_check_workflow_service
    ] = lambda: FakeWorkflowService()

    try:
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

        status_payload = (
            status_response.json()
        )

        assert (
            status_payload["result_ready"]
            is True
        )

        assert (
            status_payload["checklist_tag"]
            == "УУТЭ"
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
            == "application/json"
        )

        result_payload = (
            result_response.json()
        )

        assert (
            result_payload[
                "metadata"
            ][
                "checklist_tag"
            ]
            == "УУТЭ"
        )

        assert (
            result_payload[
                "questions"
            ][0][
                "answer"
            ]
            == "Ответ"
        )

    finally:
        app.dependency_overrides.clear()


async def test_select_requires_file() -> None:
    """SELECT без PDF возвращает 400."""
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
        response.json()["detail"]
        == (
            "file is required "
            "for action=select"
        )
    )
