from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.dependencies import get_calendar_dependencies
from app.modules.calendar.router import admin_router
from app.modules.calendar.schemas import CalendarEventSchema
from app.modules.chat.service import AuthenticatedUser


class FakePool:
    def __init__(self) -> None:
        self.executed_queries: list[dict[str, Any]] = []

    def acquire(self) -> Any:
        pool_self = self

        class FakeConnectionContext:
            async def __aenter__(self) -> Any:
                class FakeConnection:
                    async def execute(self, query: str, *args: Any) -> str:
                        pool_self.executed_queries.append({"query": query, "args": args})
                        return "INSERT 0 1"

                return FakeConnection()

            async def __aexit__(self, *_: Any) -> None:
                pass

        return FakeConnectionContext()


def create_test_app(user: AuthenticatedUser | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router)

    admin_pool = FakePool()

    async def fake_vision(image_bytes: bytes) -> list[dict[str, Any]]:
        return [
            {
                "community_id": "wolf_ranch",
                "event_date": "2026-09-20",
                "day_of_week": "Sunday",
                "start_time_utc": "2026-09-20T14:00:00Z",
                "end_time_utc": "2026-09-20T16:00:00Z",
                "is_all_day": False,
                "title": "Fall Festival",
                "description": "Live music and food trucks",
                "location": "The Den",
                "host_type": "hoa_event",
                "fee_required": False,
                "rsvp_required": True,
                "audience_tag": "all_ages",
                "is_kids_friendly": True,
                "is_adult_friendly": True,
                "notes": "Bring lawn chairs",
            }
        ]

    app.dependency_overrides[get_calendar_dependencies] = lambda: {
        "admin_pool": admin_pool,
        "vision": fake_vision,
        "process_upload": lambda *_: None,
    }

    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user

    return app


def test_extract_endpoint_returns_typed_events_for_admin() -> None:
    app = create_test_app(AuthenticatedUser(id="admin-1", role="admin"))
    client = TestClient(app)

    response = client.post(
        "/api/v1/admin/calendar/extract",
        files={"image": ("calendar.png", b"fake_png_bytes", "image/png")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    event = data["events"][0]
    assert event["title"] == "Fall Festival"
    assert event["location"] == "The Den"
    assert event["audience_tag"] == "all_ages"
    assert event["rsvp_required"] is True


def test_extract_endpoint_denies_regular_user() -> None:
    app = create_test_app(AuthenticatedUser(id="user-1", role="user"))
    client = TestClient(app)

    response = client.post(
        "/api/v1/admin/calendar/extract",
        files={"image": ("calendar.png", b"fake_png_bytes", "image/png")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required."


def test_batch_upsert_endpoint_inserts_events_for_admin() -> None:
    app = create_test_app(AuthenticatedUser(id="admin-1", role="admin"))
    client = TestClient(app)

    payload = {
        "events": [
            {
                "community_id": "wolf_ranch",
                "event_date": "2026-09-22",
                "day_of_week": "Tuesday",
                "start_time_utc": "2026-09-22T18:00:00Z",
                "end_time_utc": "2026-09-22T19:00:00Z",
                "is_all_day": False,
                "title": "Yoga in the Park",
                "description": "Sunset flow",
                "location": "River Camp",
                "host_type": "paid_fitness",
                "fee_required": True,
                "rsvp_required": False,
                "audience_tag": "adult_friendly",
                "is_kids_friendly": False,
                "is_adult_friendly": True,
                "notes": "Bring yoga mat",
            }
        ]
    }

    response = client.post("/api/v1/admin/calendar/batch-upsert", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["inserted"] == 1
    assert data["updated"] == 0


def test_batch_upsert_endpoint_denies_regular_user() -> None:
    app = create_test_app(AuthenticatedUser(id="user-1", role="user"))
    client = TestClient(app)

    payload = {
        "events": [
            {
                "community_id": "wolf_ranch",
                "event_date": "2026-09-22",
                "title": "Unauthorized Event",
            }
        ]
    }

    response = client.post("/api/v1/admin/calendar/batch-upsert", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required."
