from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


class QueryInProgressError(RuntimeError):
    """Raised when another query already owns the user's processing lock."""


class QuotaExceededError(RuntimeError):
    """Raised when a user has exhausted the rolling query quota."""


QUOTA_LIMIT = 5
QUOTA_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class QuotaStatus:
    is_unlimited: bool
    limit: int | None
    used: int
    remaining: int | None
    window: str
    resets_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_unlimited": self.is_unlimited,
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "window": self.window,
            "resets_at": self.resets_at.isoformat() if self.resets_at else None,
        }


@asynccontextmanager
async def user_query_lock(redis: Any, user_id: str) -> AsyncGenerator[None]:
    key = f"lock:user:{user_id}"
    acquired = await redis.set(key, 1, nx=True, ex=30)
    if not acquired:
        raise QueryInProgressError("A query is currently processing. Please wait.")

    try:
        yield
    finally:
        await redis.delete(key)


def rolling_quota_key(user_id: str) -> str:
    return f"rate_limit:quota:{user_id}:rolling-7d"


def unlimited_quota_status() -> QuotaStatus:
    return QuotaStatus(True, None, 0, None, "rolling_7_days", None)


def _utc_now(value: datetime | None = None) -> datetime:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc)


async def get_rolling_quota_status(redis: Any, user_id: str, now: datetime | None = None) -> QuotaStatus:
    timestamp = _utc_now(now)
    key = rolling_quota_key(user_id)
    cutoff_ms = int((timestamp - QUOTA_WINDOW).timestamp() * 1000)
    await redis.zremrangebyscore(key, -1e20, cutoff_ms)
    used = await redis.zcard(key)
    oldest = await redis.zrange(key, 0, 0)
    resets_at = None
    if oldest:
        oldest_ms = int(oldest[0].split(":", 1)[0])
        resets_at = datetime.fromtimestamp(oldest_ms / 1000, timezone.utc) + QUOTA_WINDOW
    return QuotaStatus(
        False,
        QUOTA_LIMIT,
        used,
        max(0, QUOTA_LIMIT - used),
        "rolling_7_days",
        resets_at,
    )


async def reserve_rolling_quota_slot(
    redis: Any,
    user_id: str,
    now: datetime | None = None,
) -> tuple[str, QuotaStatus]:
    timestamp = _utc_now(now)
    status = await get_rolling_quota_status(redis, user_id, timestamp)
    if status.remaining == 0:
        raise QuotaExceededError("Weekly question quota exceeded.")
    member = f"{int(timestamp.timestamp() * 1000)}:{uuid4().hex}"
    key = rolling_quota_key(user_id)
    await redis.zadd(key, timestamp.timestamp() * 1000, member)
    await redis.expire(key, int(QUOTA_WINDOW.total_seconds()))
    return member, await get_rolling_quota_status(redis, user_id, timestamp)


async def release_rolling_quota_slot(redis: Any, user_id: str, member: str) -> None:
    await redis.zrem(rolling_quota_key(user_id), member)
