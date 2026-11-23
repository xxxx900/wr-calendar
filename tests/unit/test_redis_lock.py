import asyncio
from datetime import datetime, timezone

import pytest

from app.core.redis_lock import (
    QueryInProgressError,
    get_rolling_quota_status,
    reserve_rolling_quota_slot,
    rolling_quota_key,
    user_query_lock,
)


class FakeRedis:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired
        self.deleted_keys: list[str] = []

    async def set(self, key: str, value: int, *, nx: bool, ex: int) -> bool:
        assert (value, nx, ex) == (1, True, 30)
        return self.acquired

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


def test_user_query_lock_releases_after_body_failure() -> None:
    redis = FakeRedis()

    async def run() -> None:
        with pytest.raises(RuntimeError):
            async with user_query_lock(redis, "user-1"):
                raise RuntimeError("downstream failure")

    asyncio.run(run())

    assert redis.deleted_keys == ["lock:user:user-1"]


def test_user_query_lock_rejects_existing_lock() -> None:
    redis = FakeRedis(acquired=False)

    async def run() -> None:
        with pytest.raises(QueryInProgressError):
            async with user_query_lock(redis, "user-1"):
                pass

    asyncio.run(run())

    assert redis.deleted_keys == []


def test_rolling_quota_key_is_user_scoped() -> None:
    assert rolling_quota_key("user-1") == "rate_limit:quota:user-1:rolling-7d"


def test_rolling_quota_expires_entries_after_seven_days() -> None:
    class QuotaRedis:
        def __init__(self) -> None:
            self.entries: dict[str, list[tuple[float, str]]] = {}

        async def zadd(self, key: str, score: float, member: str) -> int:
            self.entries.setdefault(key, []).append((score, member))
            return 1

        async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
            before = self.entries.get(key, [])
            self.entries[key] = [entry for entry in before if not minimum <= entry[0] <= maximum]
            return len(before) - len(self.entries[key])

        async def zcard(self, key: str) -> int:
            return len(self.entries.get(key, []))

        async def zrange(self, key: str, start: int, stop: int) -> list[str]:
            values = [member for _, member in sorted(self.entries.get(key, []))]
            return values[start:stop + 1]

        async def expire(self, _key: str, _seconds: int) -> bool:
            return True

    redis = QuotaRedis()
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)

    async def run() -> None:
        for _ in range(5):
            await reserve_rolling_quota_slot(redis, "user-1", now)
        status = await get_rolling_quota_status(redis, "user-1", now)
        assert status.remaining == 0
        expired_status = await get_rolling_quota_status(
            redis, "user-1", now.replace(day=16)
        )
        assert expired_status.used == 0

    asyncio.run(run())
