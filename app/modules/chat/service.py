from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from app.core.redis_lock import (
    QuotaExceededError,
    QuotaStatus,
    QueryInProgressError,
    get_rolling_quota_status,
    release_rolling_quota_slot,
    reserve_rolling_quota_slot,
    unlimited_quota_status,
    user_query_lock,
)
from app.core.security import PIISanitizer, build_idempotency_hash


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role in {"admin", "calendar_admin", "event_admin"}


@dataclass(frozen=True)
class QueryResult:
    payload: dict[str, Any]
    idempotency_hash: str
    quota: QuotaStatus
    turn_id: str | None = None


Pipeline = Callable[[str, AuthenticatedUser], Awaitable[dict[str, Any]]]
PersistTurn = Callable[[AuthenticatedUser, str, str, dict[str, Any]], Awaitable[str | None]]


async def run_chat_query(
    *,
    redis: Any,
    user: AuthenticatedUser,
    raw_question: str,
    pipeline: Pipeline,
    persist_turn: PersistTurn,
    now: datetime | None = None,
    enforce_quota: bool = True,
) -> QueryResult:
    idempotency_hash = build_idempotency_hash(user.id, raw_question, now)
    cached_payload = await redis.get(f"idempotency:{idempotency_hash}")
    if cached_payload is not None:
        quota = (
            unlimited_quota_status()
            if user.is_admin or not enforce_quota
            else await get_rolling_quota_status(redis, user.id, now)
        )
        return QueryResult(payload=cached_payload, idempotency_hash=idempotency_hash, quota=quota)

    PIISanitizer.reject_if_high_risk(raw_question)

    try:
        async with user_query_lock(redis, user.id):
            reservation = None
            quota = unlimited_quota_status()
            if enforce_quota and not user.is_admin:
                reservation, quota = await reserve_rolling_quota_slot(redis, user.id, now)
            try:
                payload = await pipeline(raw_question, user)
                turn_id = await persist_turn(user, raw_question, idempotency_hash, payload)
                await redis.set(f"idempotency:{idempotency_hash}", payload, ex=60 * 60)
                return QueryResult(
                    payload=payload,
                    idempotency_hash=idempotency_hash,
                    quota=quota,
                    turn_id=turn_id,
                )
            except Exception:
                if reservation is not None:
                    await release_rolling_quota_slot(redis, user.id, reservation)
                raise
    except QueryInProgressError:
        raise


async def update_feedback(
    *,
    user: AuthenticatedUser,
    turn_id: str,
    rating: str,
    comment: str | None,
    update_feedback_columns: Callable[[str, str, str, str | None], Awaitable[None]],
    now: datetime | None,
) -> None:
    await update_feedback_columns(turn_id, user.id, rating, comment)
