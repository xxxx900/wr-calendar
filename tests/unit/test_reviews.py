from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.core.auth import get_current_user, get_optional_current_user
from app.modules.chat.service import AuthenticatedUser
from app.modules.reviews.router import get_reviews_service, router as reviews_router
from app.modules.reviews.schemas import ReactionToggleRequest, ReviewUpsertRequest
from app.modules.reviews.service import CENTRAL_TZ, ReviewsService, get_today_central


class InMemoryReviewsPool:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {
            "evt-past": {
                "id": "evt-past",
                "event_date": (datetime.now(CENTRAL_TZ).date() - timedelta(days=2)).isoformat(),
                "title": "Past Coffee Social",
                "review_count": 1,
                "average_rating": 5.0,
                "attended_count": 1,
                "reaction_counts": {"going": 0, "love": 3, "helpful": 1},
                "is_deleted": False,
            },
            "evt-future": {
                "id": "evt-future",
                "event_date": (datetime.now(CENTRAL_TZ).date() + timedelta(days=5)).isoformat(),
                "title": "Future Pool Party",
                "review_count": 0,
                "average_rating": None,
                "attended_count": 0,
                "reaction_counts": {"going": 10, "love": 4, "helpful": 0},
                "is_deleted": False,
            },
            "evt-today": {
                "id": "evt-today",
                "event_date": datetime.now(CENTRAL_TZ).date().isoformat(),
                "title": "Today Sunset Yoga",
                "review_count": 0,
                "average_rating": None,
                "attended_count": 0,
                "reaction_counts": {"going": 5, "love": 2, "helpful": 1},
                "is_deleted": False,
            },
        }
        self.reviews: list[dict[str, Any]] = [
            {
                "id": "rev-1",
                "event_id": "evt-past",
                "user_id": "user-neighbor-1",
                "rating": 5,
                "comment": "Had an amazing time!",
                "attended_event": True,
                "is_anonymous": True,
                "is_deleted": False,
                "created_at": datetime.now(timezone.utc) - timedelta(days=1),
                "updated_at": datetime.now(timezone.utc) - timedelta(days=1),
                "user_email": "neighbor1@example.com",
            }
        ]
        self.reactions: dict[tuple[str, str], str] = {
            ("evt-past", "user-neighbor-1"): "love"
        }

    def acquire(self) -> Any:
        pool_self = self

        class ConnectionContext:
            async def __aenter__(self) -> Any:
                class Connection:
                    async def fetchrow(self, query: str, *args: Any) -> Any:
                        if "FROM events" in query:
                            event_id = args[0]
                            event = pool_self.events.get(event_id)
                            if not event or event.get("is_deleted"):
                                return None
                            return {
                                "id": event["id"],
                                "event_date": event["event_date"],
                                "title": event["title"],
                                "review_count": event["review_count"],
                                "average_rating": event["average_rating"],
                                "attended_count": event["attended_count"],
                                "reaction_counts": event["reaction_counts"],
                            }
                        if "FROM event_reactions" in query:
                            event_id, user_id = args[0], args[1]
                            rx = pool_self.reactions.get((event_id, user_id))
                            return {"reaction_type": rx} if rx else None
                        if "FROM event_reviews" in query:
                            event_id, user_id = args[0], args[1]
                            for r in pool_self.reviews:
                                if r["event_id"] == event_id and r["user_id"] == user_id and not r["is_deleted"]:
                                    return r
                            return None
                        if "INSERT INTO event_reviews" in query or "UPDATE event_reviews" in query:
                            # Upsert review simulation
                            if "UPDATE event_reviews" in query and "is_deleted = TRUE" in query:
                                return None
                            if "UPDATE" in query:
                                r_id = args[4]
                                for r in pool_self.reviews:
                                    if r["id"] == r_id:
                                        r["rating"] = args[0]
                                        r["comment"] = args[1]
                                        r["attended_event"] = args[2]
                                        r["is_anonymous"] = args[3]
                                        r["updated_at"] = datetime.now(timezone.utc)
                                        return r
                            else:
                                new_rev = {
                                    "id": f"rev-{len(pool_self.reviews) + 1}",
                                    "event_id": args[0],
                                    "user_id": args[1],
                                    "rating": args[2],
                                    "comment": args[3],
                                    "attended_event": args[4],
                                    "is_anonymous": args[5],
                                    "is_deleted": False,
                                    "created_at": datetime.now(timezone.utc),
                                    "updated_at": datetime.now(timezone.utc),
                                }
                                pool_self.reviews.append(new_rev)
                                return new_rev
                        return None

                    async def fetch(self, query: str, *args: Any) -> list[Any]:
                        if "GROUP BY rating" in query:
                            event_id = args[0]
                            dist: dict[int, int] = {}
                            for r in pool_self.reviews:
                                if r["event_id"] == event_id and not r["is_deleted"]:
                                    dist[r["rating"]] = dist.get(r["rating"], 0) + 1
                            return [{"rating": k, "count": v} for k, v in dist.items()]
                        if "FROM event_reviews" in query:
                            event_id = args[0]
                            res: list[dict[str, Any]] = []
                            for r in pool_self.reviews:
                                if r["event_id"] == event_id and not r["is_deleted"]:
                                    res.append(r)
                            return res
                        return []

                    async def fetchval(self, query: str, *args: Any) -> Any:
                        if "SELECT id::text FROM event_reviews" in query:
                            event_id, user_id = args[0], args[1]
                            for r in pool_self.reviews:
                                if r["event_id"] == event_id and r["user_id"] == user_id and not r["is_deleted"]:
                                    return r["id"]
                            return None
                        if "UPDATE event_reviews" in query and "is_deleted = TRUE" in query:
                            event_id = args[0]
                            user_id = args[1] if len(args) > 1 else None
                            for r in pool_self.reviews:
                                if r["event_id"] == event_id and not r["is_deleted"]:
                                    if user_id is None or r["user_id"] == user_id:
                                        r["is_deleted"] = True
                                        r["deleted_at"] = datetime.now(timezone.utc)
                                        return r["id"]
                            return None
                        if "SELECT reaction_type FROM event_reactions" in query:
                            event_id, user_id = args[0], args[1]
                            return pool_self.reactions.get((event_id, user_id))
                        if "SELECT reaction_counts FROM events" in query:
                            event_id = args[0]
                            return pool_self.events.get(event_id, {}).get("reaction_counts", {})
                        return None

                    async def execute(self, query: str, *args: Any) -> str:
                        if "DELETE FROM event_reactions" in query:
                            event_id, user_id = args[0], args[1]
                            pool_self.reactions.pop((event_id, user_id), None)
                            ev = pool_self.events.get(event_id)
                            if ev:
                                ev["reaction_counts"]["going"] = max(0, ev["reaction_counts"].get("going", 0) - 1)
                            return "DELETE 1"
                        if "INSERT INTO event_reactions" in query:
                            event_id, user_id, reaction_type = args[0], args[1], args[2]
                            pool_self.reactions[(event_id, user_id)] = reaction_type
                            ev = pool_self.events.get(event_id)
                            if ev:
                                ev["reaction_counts"][reaction_type] = ev["reaction_counts"].get(reaction_type, 0) + 1
                            return "INSERT 0 1"
                        return "OK"

                return Connection()

            async def __aexit__(self, *_: Any) -> None:
                pass

        return ConnectionContext()


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.deleted_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> int:
        self.deleted_keys.append(key)
        return 1 if self.store.pop(key, None) else 0


import asyncio


def test_get_interactions_anonymous_and_cached() -> None:
    async def run() -> None:
        pool = InMemoryReviewsPool()
        redis = FakeRedis()
        service = ReviewsService(admin_pool=pool, redis=redis)

        # First call loads from pool and caches in Redis
        res1 = await service.get_interactions("evt-past", user_id=None)
        assert res1.event_id == "evt-past"
        assert res1.user_reaction is None
        assert "cache:event_interactions:evt-past" in redis.store

        # Second call reads from Redis
        res2 = await service.get_interactions("evt-past", user_id=None)
        assert res2.review_count == res1.review_count

    asyncio.run(run())


def test_get_reviews_anonymity_masking() -> None:
    async def run() -> None:
        pool = InMemoryReviewsPool()
        service = ReviewsService(admin_pool=pool)

        # Viewer is another user -> review is masked as 'Neighbor'
        reviews_res = await service.get_reviews("evt-past", user_id="user-stranger")
        assert len(reviews_res.reviews) == 1
        rev = reviews_res.reviews[0]
        assert rev.is_anonymous is True
        assert rev.is_author is False
        assert rev.author_name == "Neighbor"

        # Viewer is the author -> review shows 'You (Anonymous to neighbors)'
        author_res = await service.get_reviews("evt-past", user_id="user-neighbor-1")
        author_rev = author_res.reviews[0]
        assert author_rev.is_author is True
        assert "You" in author_rev.author_name

    asyncio.run(run())


def test_future_event_review_rejected() -> None:
    async def run() -> None:
        pool = InMemoryReviewsPool()
        service = ReviewsService(admin_pool=pool)

        req = ReviewUpsertRequest(
            rating=5,
            comment="Excited for this future event!",
            attended_event=False,
            is_anonymous=False,
        )

        with pytest.raises(Exception) as exc_info:
            await service.post_review("evt-future", user_id="user-test", payload=req)
        assert "Reviews and attendance unlock once this event occurs" in str(exc_info.value)

    asyncio.run(run())


def test_past_event_going_reaction_rejected() -> None:
    async def run() -> None:
        pool = InMemoryReviewsPool()
        service = ReviewsService(admin_pool=pool)

        with pytest.raises(Exception) as exc_info:
            await service.toggle_event_reaction("evt-past", user_id="user-test", reaction_type="going")
        assert "Planning to go" in str(exc_info.value)

    asyncio.run(run())


def test_past_event_love_reaction_allowed_and_cache_cleared() -> None:
    async def run() -> None:
        pool = InMemoryReviewsPool()
        redis = FakeRedis()
        service = ReviewsService(admin_pool=pool, redis=redis)

        res = await service.toggle_event_reaction("evt-past", user_id="user-test", reaction_type="love")
        assert res.reaction_type == "love"
        assert "cache:event_interactions:evt-past" in redis.deleted_keys

    asyncio.run(run())


def test_soft_delete_review() -> None:
    async def run() -> None:
        pool = InMemoryReviewsPool()
        redis = FakeRedis()
        service = ReviewsService(admin_pool=pool, redis=redis)

        # Author soft-deletes their review
        del_res = await service.delete_review("evt-past", user_id="user-neighbor-1", is_admin=False)
        assert del_res["status"] == "review_deleted"
        assert pool.reviews[0]["is_deleted"] is True
        assert "cache:event_interactions:evt-past" in redis.deleted_keys

    asyncio.run(run())


def test_router_endpoints_with_testclient() -> None:
    app = FastAPI()
    app.include_router(reviews_router)

    pool = InMemoryReviewsPool()
    redis = FakeRedis()
    service = ReviewsService(admin_pool=pool, redis=redis)

    app.dependency_overrides[get_reviews_service] = lambda: service
    app.dependency_overrides[get_optional_current_user] = lambda: AuthenticatedUser(
        id="user-neighbor-1", role="user"
    )
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id="user-neighbor-1", role="user"
    )

    client = TestClient(app)

    # 1. GET interactions
    r = client.get("/api/v1/events/evt-past/interactions")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["event_id"] == "evt-past"
    assert "going" in data["reaction_counts"]
    assert data["user_reaction"] == "love"

    # 2. GET reviews
    r = client.get("/api/v1/events/evt-past/reviews?sort=rating_desc")
    assert r.status_code == status.HTTP_200_OK
    rev_data = r.json()
    assert rev_data["event_id"] == "evt-past"
    assert "star_distribution" in rev_data
