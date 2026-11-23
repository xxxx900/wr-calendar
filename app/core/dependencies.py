from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.modules.chat.repository import persist_turn, update_feedback_columns
from app.modules.chat.service import AuthenticatedUser


async def get_chat_dependencies(request: Request) -> dict[str, Any]:
    pools = getattr(request.app.state, "pools", None)
    redis = getattr(request.app.state, "redis", None)
    pipeline = getattr(request.app.state, "chat_pipeline", None)
    if pools is None or redis is None or pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chat is unavailable.")

    async def save_turn(
        user: AuthenticatedUser,
        raw_question: str,
        idempotency_hash: str,
        payload: dict[str, Any],
    ) -> str | None:
        if get_settings().local_development:
            return None
        return await persist_turn(pools.admin, user.id, raw_question, idempotency_hash, payload)

    async def save_feedback(
        turn_id: str,
        user_id: str,
        rating: str,
        comment: str | None,
    ) -> None:
        await update_feedback_columns(pools.admin, turn_id, user_id, rating, comment)

    return {
        "redis": redis,
        "pipeline": pipeline,
        "admin_pool": pools.admin,
        "persist_turn": save_turn,
        "update_feedback_columns": save_feedback,
    }


async def get_calendar_dependencies(request: Request) -> dict[str, Any]:
    pools = getattr(request.app.state, "pools", None)
    vision = getattr(request.app.state, "vision", None)
    process_upload = getattr(request.app.state, "process_calendar_upload", None)
    if pools is None or vision is None or process_upload is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Calendar is unavailable.")
    return {
        "admin_pool": pools.admin,
        "vision": vision,
        "process_upload": process_upload,
    }


async def get_calendar_read_dependencies(request: Request) -> dict[str, Any]:
    pools = getattr(request.app.state, "pools", None)
    if pools is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Calendar is unavailable.")
    return {"readonly_pool": pools.readonly}
