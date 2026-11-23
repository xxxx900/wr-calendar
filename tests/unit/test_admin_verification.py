from __future__ import annotations

from typing import Any
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_chat_dependencies
from app.modules.chat import router as chat_router_module
from app.modules.chat.router import router as chat_router


class FakePool:
    def __init__(self, admin_emails: list[str]) -> None:
        self.admin_emails = [e.lower() for e in admin_emails]

    def acquire(self) -> Any:
        pool_self = self

        class FakeConnectionContext:
            async def __aenter__(self) -> Any:
                class FakeConnection:
                    async def fetchval(self, query: str, email: str) -> str | None:
                        if email.lower() in pool_self.admin_emails:
                            return "admin"
                        return "user"

                return FakeConnection()

            async def __aexit__(self, *_: Any) -> None:
                pass

        return FakeConnectionContext()


def test_verify_admin_endpoint_identifies_admin_via_google_token(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(chat_router)

    pool = FakePool(["admin@example.com"])

    app.dependency_overrides[get_chat_dependencies] = lambda: {
        "redis": None,
        "pipeline": None,
        "admin_pool": pool,
        "persist_turn": lambda *_: None,
        "update_feedback_columns": lambda *_: None,
    }

    async def fake_verify(token: str) -> dict[str, Any]:
        if token == "valid-google-token":
            return {"email": "admin@example.com", "name": "Admin User"}
        if token == "invalid-token":
            raise HTTPException(status_code=401, detail="Invalid Google provider token.")
        return {"email": "user@example.com", "name": "Regular User"}

    monkeypatch.setattr(chat_router_module, "verify_google_oauth_token", fake_verify)

    client = TestClient(app)

    # Test Admin Token
    response = client.post("/api/v1/chat/auth/verify-admin", json={"provider_token": "valid-google-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_admin"] is True
    assert data["email"] == "admin@example.com"
    assert data["name"] == "Admin User"

    # Test Regular User Token
    response = client.post("/api/v1/chat/auth/verify-admin", json={"provider_token": "other-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_admin"] is False
    assert data["email"] == "user@example.com"

    # Test Invalid Google Token
    response = client.post("/api/v1/chat/auth/verify-admin", json={"provider_token": "invalid-token"})
    assert response.status_code == 401
