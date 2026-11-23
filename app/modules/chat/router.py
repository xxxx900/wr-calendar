from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import check_user_is_admin_in_db, get_current_user, verify_google_oauth_token
from app.core.config import get_settings
from app.core.dependencies import get_chat_dependencies
from app.core.redis_lock import (
    QueryInProgressError,
    QuotaStatus,
    get_rolling_quota_status,
    unlimited_quota_status,
)
from app.modules.chat.service import (
    AuthenticatedUser,
    QuotaExceededError,
    run_chat_query,
    update_feedback,
)
from app.modules.chat.openai_provider import OpenAIProviderError

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class FeedbackRequest(BaseModel):
    turn_id: str
    rating: str
    comment: str | None = Field(default=None, max_length=4000)


class AdminVerificationRequest(BaseModel):
    provider_token: str = Field(min_length=1)


class AdminVerificationResponse(BaseModel):
    is_admin: bool
    email: str
    name: str | None = None
    picture: str | None = None


@router.post("/auth/verify-admin", response_model=AdminVerificationResponse)
async def verify_admin_status(
    request: AdminVerificationRequest,
    dependencies: dict[str, Any] = Depends(get_chat_dependencies),
) -> AdminVerificationResponse:
    google_user = await verify_google_oauth_token(request.provider_token)
    email = google_user.get("email", "")
    is_admin = await check_user_is_admin_in_db(
        dependencies.get("admin_pool"),
        email,
        get_settings(),
    )
    return AdminVerificationResponse(
        is_admin=is_admin,
        email=email,
        name=google_user.get("name"),
        picture=google_user.get("picture"),
    )


@router.post("/query")
async def query_chat(
    request: QueryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    dependencies: dict[str, Any] = Depends(get_chat_dependencies),
) -> dict[str, Any]:
    try:
        result = await run_chat_query(
            redis=dependencies["redis"],
            user=user,
            raw_question=request.question,
            pipeline=dependencies["pipeline"],
            persist_turn=dependencies["persist_turn"],
            enforce_quota=not get_settings().local_development,
        )
    except QueryInProgressError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OpenAIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The calendar assistant is temporarily unavailable.",
        ) from exc

    quota_dict = result.quota.as_dict()
    if user.is_admin and dependencies.get("admin_pool"):
        try:
            async with dependencies["admin_pool"].acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_turns WHERE user_id = $1::uuid",
                    user.id,
                ) or 0
                quota_dict["used"] = int(count)
        except Exception:
            pass

    return {
        "idempotency_hash": result.idempotency_hash,
        "turn_id": result.turn_id,
        "payload": result.payload,
        "quota": quota_dict,
    }


@router.get("/quota")
async def get_quota(
    user: AuthenticatedUser = Depends(get_current_user),
    dependencies: dict[str, Any] = Depends(get_chat_dependencies),
) -> dict[str, Any]:
    if user.is_admin:
        admin_used = 0
        if dependencies.get("admin_pool"):
            try:
                async with dependencies["admin_pool"].acquire() as conn:
                    admin_used = await conn.fetchval(
                        "SELECT COUNT(*) FROM user_turns WHERE user_id = $1::uuid",
                        user.id,
                    ) or 0
            except Exception:
                pass
        quota = QuotaStatus(True, None, int(admin_used), None, "unlimited", None)
    elif get_settings().local_development:
        quota = unlimited_quota_status()
    else:
        quota = await get_rolling_quota_status(dependencies["redis"], user.id)
    return {"quota": quota.as_dict()}


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(
    request: FeedbackRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    dependencies: dict[str, Any] = Depends(get_chat_dependencies),
) -> None:
    if request.rating not in {"thumbs_up", "thumbs_down"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid rating.")

    try:
        await update_feedback(
            user=user,
            turn_id=request.turn_id,
            rating=request.rating,
            comment=request.comment,
            update_feedback_columns=dependencies["update_feedback_columns"],
            now=None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
