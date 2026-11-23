from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user
from app.core.dependencies import get_calendar_dependencies, get_calendar_read_dependencies
from app.modules.calendar.repository import fetch_month_events, upsert_events
from app.modules.calendar.schemas import (
    BatchUpsertRequest,
    BatchUpsertResponse,
    CalendarEventSchema,
    ExtractionResponse,
)
from app.modules.calendar.service import extract_calendar_events, stream_calendar_ingestion
from app.modules.chat.service import AuthenticatedUser

router = APIRouter(prefix="/api/v1", tags=["calendar"])


@router.get("/calendar/current-month")
async def get_current_month_calendar(
    month: str | None = None,
    dependencies: dict[str, Any] = Depends(get_calendar_read_dependencies),
) -> dict[str, Any]:
    requested_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        month_start = date.fromisoformat(f"{requested_month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must use YYYY-MM format.") from exc
    if requested_month != month_start.strftime("%Y-%m"):
        raise HTTPException(status_code=400, detail="month must use YYYY-MM format.")

    events = await fetch_month_events(dependencies["readonly_pool"], month_start)
    return {
        "month": requested_month,
        "events": events,
        "count": len(events),
    }


admin_router = APIRouter(prefix="/api/v1/admin/calendar", tags=["calendar"])


@admin_router.post("/extract", response_model=ExtractionResponse)
async def extract_calendar(
    image: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    dependencies: dict[str, Any] = Depends(get_calendar_dependencies),
) -> ExtractionResponse:
    if user.role not in {"admin", "calendar_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is empty.")

    try:
        extracted = await extract_calendar_events(image_bytes, dependencies["vision"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Extraction failed: {exc}") from exc

    events = [CalendarEventSchema.model_validate(e) for e in extracted]
    return ExtractionResponse(events=events, count=len(events))


@admin_router.post("/batch-upsert", response_model=BatchUpsertResponse)
async def batch_upsert_calendar_events(
    request: BatchUpsertRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    dependencies: dict[str, Any] = Depends(get_calendar_dependencies),
) -> BatchUpsertResponse:
    if user.role not in {"admin", "calendar_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")

    events_dict = [e.model_dump() for e in request.events]
    result = await upsert_events(dependencies["admin_pool"], events_dict)
    return BatchUpsertResponse(inserted=result["inserted"], updated=result["updated"])


@admin_router.post("/ingest/stream")
async def ingest_calendar(
    image: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    dependencies: dict[str, Any] = Depends(get_calendar_dependencies),
) -> EventSourceResponse:
    if user.role not in {"admin", "calendar_admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is empty.")

    async def events() -> Any:
        async for event in stream_calendar_ingestion(
            image_bytes,
            lambda payload, queue: dependencies["process_upload"](payload, queue),
        ):
            yield event

    return EventSourceResponse(events(), ping=0)
