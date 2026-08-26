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
from app.domain.enums import ChecklistCode

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
    file: Annotated[
        UploadFile | None,
        File(),
    ] = None,
) -> (
    TzCheckSelectResponse
    | TzCheckConfirmResponse
    | TzCheckStatusResponse
    | Response
):
    """Выполнить одну операцию lifecycle ТЗ через единый endpoint."""
    try:
        if action == TzCheckAction.SELECT:
            return await _select(
                service=service,
                file=file,
            )

        if action == TzCheckAction.CONFIRM:
            return _confirm(
                service=service,
                request_id=request_id,
                checklist_code=checklist_code,
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

        # StrEnum + FastAPI validation фактически
        # не позволяет попасть сюда.
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
) -> TzCheckSelectResponse:
    """Обработать action=select."""
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

    try:
        pdf_bytes = await file.read()
    finally:
        await file.close()

    result = await service.select(
        pdf_bytes
    )

    suggestion = (
        result
        .selection
        .suggestion
    )

    return TzCheckSelectResponse(
        request_id=result.request_id,
        recommended_checklist=(
            suggestion.recommended_code
        ),
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
) -> TzCheckConfirmResponse:
    """Обработать action=confirm."""
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

    if checklist_code is None:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "checklist_code is required "
                "for action=confirm"
            ),
        )

    result = service.confirm(
        request_id=request_id,
        checklist_code=checklist_code,
    )

    return TzCheckConfirmResponse(
        request_id=result.request_id,
        status=result.status,
        checklist_code=(
            result.checklist.code
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
    """Обработать action=status."""
    required_id = _require_request_id(
        request_id,
        action=TzCheckAction.STATUS,
    )

    result = service.status(
        required_id
    )

    return TzCheckStatusResponse(
        request_id=result.request_id,
        status=result.status,
        checklist_code=result.checklist_code,
        progress_percent=result.progress_percent,
        result_ready=result.result_ready,
        error=result.error,
    )


def _result(
    *,
    service: TzCheckWorkflowService,
    request_id: UUID | None,
) -> Response:
    """Обработать одноразовую выдачу PDF."""
    required_id = _require_request_id(
        request_id,
        action=TzCheckAction.RESULT,
    )

    pdf_bytes = service.result(
        required_id
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="tz-checklist-{required_id}.pdf"'
            ),
            # Ни браузер, ни reverse proxy не должны
            # кешировать пользовательский отчёт.
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


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
