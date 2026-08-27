# app/api/v1/tz_check.py

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_tz_check_workflow_service,
)
from app.api.v1.schemas import (
    ChecklistRankingResponse,
    TzCheckAction,
    TzCheckConfirmResponse,
    TzCheckSelectResponse,
    TzCheckStatusResponse,
    TzCheckTaggedSelectResponse,
)
from app.application.errors import (
    InvalidJobStateError,
    InvalidPdfError,
    JobNotFoundError,
    QueueSubmissionError,
    ResultNotReadyError,
    UploadTooLargeError,
)
from app.application.services.tz_check_workflow_service import (
    TzCheckWorkflowService,
)
from app.domain.enums import (
    ChecklistCode,
    ChecklistTag,
)
from app.domain.workflow import (
    WorkflowTaggedSubmissionResult,
)

router = APIRouter(
    tags=[
        "tz-check",
    ]
)


@router.post(
    "/api/v1/tz-check",
    response_model=None,
)
async def tz_check(
    action: Annotated[
        TzCheckAction,
        Form(),
    ],
    service: Annotated[
        TzCheckWorkflowService,
        Depends(
            get_tz_check_workflow_service
        ),
    ],
    request_id: Annotated[
        UUID | None,
        Form(),
    ] = None,
    checklist_code: Annotated[
        ChecklistCode | None,
        Form(),
    ] = None,
    checklist_tag: Annotated[
        ChecklistTag | None,
        Form(),
    ] = None,
    file: Annotated[
        UploadFile | None,
        File(),
    ] = None,
) -> (
    TzCheckSelectResponse
    | TzCheckTaggedSelectResponse
    | TzCheckConfirmResponse
    | TzCheckStatusResponse
    | Response
):
    """Выполнить одну операцию lifecycle ТЗ."""
    try:
        if action == TzCheckAction.SELECT:
            return await _select(
                service=service,
                file=file,
                checklist_tag=checklist_tag,
            )

        if action == TzCheckAction.CONFIRM:
            return _confirm(
                service=service,
                request_id=request_id,
                checklist_code=checklist_code,
                checklist_tag=checklist_tag,
            )

        if action == TzCheckAction.STATUS:
            return _status(
                service=service,
                request_id=request_id,
            )

        if action == TzCheckAction.RESULT:
            return _result(
                service=service,
                request_id=request_id,
            )

        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Unknown action",
        )

    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=str(exc),
        ) from exc

    except InvalidPdfError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    except (
        InvalidJobStateError,
        ResultNotReadyError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except QueueSubmissionError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc


async def _select(
    *,
    service: TzCheckWorkflowService,
    file: UploadFile | None,
    checklist_tag: ChecklistTag | None,
) -> (
    TzCheckSelectResponse
    | TzCheckTaggedSelectResponse
):
    """Обработать SELECT с optional tag."""
    if file is None:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "file is required "
                "for action=select"
            ),
        )

    source_filename = (
        file.filename
        or "document.pdf"
    )

    try:
        pdf_bytes = await file.read()
    finally:
        await file.close()

    result = await service.select(
        pdf_bytes,
        source_filename=source_filename,
        checklist_tag=checklist_tag,
    )

    if isinstance(
        result,
        WorkflowTaggedSubmissionResult,
    ):
        return TzCheckTaggedSelectResponse(
            request_id=result.request_id,
            checklist_code=(
                result.checklist.code
            ),
            checklist_tag=(
                result.checklist_tag
            ),
            checklist_title=(
                result.checklist.title
            ),
        )

    suggestion = (
        result
        .selection
        .suggestion
    )

    recommended_tag = (
        ChecklistTag.from_code(
            suggestion.recommended_code
        )
        if suggestion.recommended_code
        is not None
        else None
    )

    return TzCheckSelectResponse(
        request_id=result.request_id,
        recommended_checklist=(
            suggestion.recommended_code
        ),
        recommended_tag=recommended_tag,
        confidence=suggestion.confidence,
        requires_confirmation=(
            suggestion.requires_confirmation
        ),
        ranking=[
            ChecklistRankingResponse(
                code=item.code,
                score=item.score,
                matched_hints=list(
                    item.matched_hints
                ),
            )
            for item
            in suggestion.ranking
        ],
        classification_source=(
            result.selection.source
        ),
        fallback_reason=(
            result.selection.fallback_reason
        ),
        vision_pages=list(
            result.selection.vision_pages
        ),
    )


def _confirm(
    *,
    service: TzCheckWorkflowService,
    request_id: UUID | None,
    checklist_code: ChecklistCode | None,
    checklist_tag: ChecklistTag | None,
) -> TzCheckConfirmResponse:
    """Подтвердить auto-detected checklist."""
    if request_id is None:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "request_id is required "
                "for action=confirm"
            ),
        )

    resolved_code = _resolve_confirm_code(
        checklist_code=checklist_code,
        checklist_tag=checklist_tag,
    )

    result = service.confirm(
        request_id=request_id,
        checklist_code=resolved_code,
    )

    return TzCheckConfirmResponse(
        request_id=result.request_id,
        status=result.status,
        checklist_code=(
            result.checklist.code
        ),
        checklist_tag=(
            ChecklistTag.from_code(
                result.checklist.code
            )
        ),
        checklist_title=(
            result.checklist.title
        ),
    )


def _status(
    *,
    service: TzCheckWorkflowService,
    request_id: UUID | None,
) -> TzCheckStatusResponse:
    """Получить status."""
    required_id = _require_request_id(
        request_id,
        action=TzCheckAction.STATUS,
    )

    result = service.status(
        required_id
    )

    tag = (
        ChecklistTag.from_code(
            result.checklist_code
        )
        if result.checklist_code
        is not None
        else None
    )

    return TzCheckStatusResponse(
        request_id=result.request_id,
        status=result.status,
        checklist_code=result.checklist_code,
        checklist_tag=tag,
        progress_percent=result.progress_percent,
        result_ready=result.result_ready,
        error=result.error,
    )


def _result(
    *,
    service: TzCheckWorkflowService,
    request_id: UUID | None,
) -> Response:
    """Одноразово вернуть JSON result."""
    required_id = _require_request_id(
        request_id,
        action=TzCheckAction.RESULT,
    )

    result_bytes = service.result(
        required_id
    )

    return Response(
        content=result_bytes,
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _resolve_confirm_code(
    *,
    checklist_code: ChecklistCode | None,
    checklist_tag: ChecklistTag | None,
) -> ChecklistCode:
    """Разрешить confirm по code либо public tag."""
    if (
        checklist_code is None
        and checklist_tag is None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "checklist_code or checklist_tag "
                "is required for action=confirm"
            ),
        )

    if (
        checklist_code is not None
        and checklist_tag is not None
        and checklist_code
        != checklist_tag.code
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "checklist_code and checklist_tag "
                "refer to different checklists"
            ),
        )

    if checklist_tag is not None:
        return checklist_tag.code

    assert checklist_code is not None

    return checklist_code


def _require_request_id(
    request_id: UUID | None,
    *,
    action: TzCheckAction,
) -> UUID:
    """Проверить обязательный request_id."""
    if request_id is None:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "request_id is required "
                f"for action={action.value}"
            ),
        )

    return request_id
