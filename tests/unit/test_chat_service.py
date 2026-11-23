import asyncio
from datetime import datetime, timezone

import pytest

from app.modules.chat.service import (
    AuthenticatedUser,
    QuotaExceededError,
    run_chat_query,
    update_feedback,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.counts: dict[str, int] = {}
        self.deleted: list[str] = []
        self.sorted_sets: dict[str, list[tuple[float, str]]] = {}

    async def get(self, key: str) -> object:
        return self.values.get(key)

    async def set(self, key: str, value: object, **_: object) -> bool:
        self.values[key] = value
        return True

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def delete(self, key: str) -> None:
        self.deleted.append(key)

    async def zadd(self, key: str, score: float, member: str) -> int:
        self.sorted_sets.setdefault(key, []).append((score, member))
        return 1

    async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        before = self.sorted_sets.get(key, [])
        self.sorted_sets[key] = [entry for entry in before if not minimum <= entry[0] <= maximum]
        return len(before) - len(self.sorted_sets[key])

    async def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, []))

    async def zrange(self, key: str, start: int, stop: int) -> list[str]:
        return [member for _, member in sorted(self.sorted_sets.get(key, []))][start:stop + 1]

    async def zrem(self, key: str, member: str) -> int:
        before = self.sorted_sets.get(key, [])
        self.sorted_sets[key] = [entry for entry in before if entry[1] != member]
        return len(before) - len(self.sorted_sets[key])


UTC_HOUR = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


def test_query_caches_pipeline_result_and_releases_lock() -> None:
    redis = FakeRedis()
    calls: list[str] = []

    async def pipeline(question: str, user: AuthenticatedUser) -> dict[str, str]:
        calls.append(question)
        return {"answer": "Saturday market"}

    async def persist(*_: object) -> None:
        return None

    async def run() -> None:
        first = await run_chat_query(
            redis=redis,
            user=AuthenticatedUser("user-1", "user"),
            raw_question=" What events are today? ",
            pipeline=pipeline,
            persist_turn=persist,
            now=UTC_HOUR,
        )
        second = await run_chat_query(
            redis=redis,
            user=AuthenticatedUser("user-1", "user"),
            raw_question="what events are today?",
            pipeline=pipeline,
            persist_turn=persist,
            now=UTC_HOUR,
        )
        assert first.payload == second.payload

    asyncio.run(run())
    assert calls == [" What events are today? "]
    assert redis.deleted == ["lock:user:user-1"]


def test_non_admin_quota_is_enforced_before_pipeline() -> None:
    redis = FakeRedis()
    redis.sorted_sets["rate_limit:quota:user-1:rolling-7d"] = [
        (UTC_HOUR.timestamp() * 1000, f"{index}:query") for index in range(5)
    ]

    async def pipeline(*_: object) -> dict[str, str]:
        raise AssertionError("pipeline should not run")

    async def persist(*_: object) -> None:
        return None

    async def run() -> None:
        with pytest.raises(QuotaExceededError):
            await run_chat_query(
                redis=redis,
                user=AuthenticatedUser("user-1", "user"),
                raw_question="What events are today?",
                pipeline=pipeline,
                persist_turn=persist,
                now=UTC_HOUR,
            )

    asyncio.run(run())


def test_local_development_can_skip_quota_for_non_admin() -> None:
    redis = FakeRedis()

    async def pipeline(question: str, user: AuthenticatedUser) -> dict[str, str]:
        return {"answer": question}

    async def persist(*_: object) -> None:
        return None

    async def run() -> None:
        result = await run_chat_query(
            redis=redis,
            user=AuthenticatedUser("user-1", "user"),
            raw_question="Local test",
            pipeline=pipeline,
            persist_turn=persist,
            enforce_quota=False,
        )
        assert result.payload == {"answer": "Local test"}

    asyncio.run(run())
    assert redis.counts == {}


def test_feedback_updates_only_through_injected_feedback_writer() -> None:
    updates: list[tuple[str, str, str, str | None]] = []

    async def update(turn_id: str, user_id: str, rating: str, comment: str | None) -> None:
        updates.append((turn_id, user_id, rating, comment))

    async def run() -> None:
        await update_feedback(
            user=AuthenticatedUser("user-1", "user"),
            turn_id="turn-1",
            rating="thumbs_up",
            comment="Helpful",
            update_feedback_columns=update,
            now=UTC_HOUR,
        )

    asyncio.run(run())
    assert updates == [("turn-1", "user-1", "thumbs_up", "Helpful")]
