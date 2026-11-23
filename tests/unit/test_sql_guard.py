import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.modules.chat.sql_guard import ReadOnlySqlGuard, UnsafeSqlError, execute_readonly


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE events SET title = 'changed'",
        "DROP TABLE events",
        "SELECT * FROM events; DELETE FROM events",
        "INSERT INTO events (title) VALUES ('bad')",
    ],
)
def test_guard_rejects_mutating_or_multiple_statements(query: str) -> None:
    with pytest.raises(UnsafeSqlError):
        ReadOnlySqlGuard.validate(query)


def test_guard_accepts_select_and_with_queries() -> None:
    assert ReadOnlySqlGuard.validate(" SELECT * FROM events; ") == "SELECT * FROM events"
    assert ReadOnlySqlGuard.validate("WITH recent AS (SELECT 1) SELECT * FROM recent")


def test_guard_rejects_numeric_date_arithmetic() -> None:
    with pytest.raises(UnsafeSqlError, match="Date arithmetic"):
        ReadOnlySqlGuard.validate("SELECT * FROM events WHERE event_date + 7 > CURRENT_DATE")


def test_sql_guard_rejects_forbidden_tables() -> None:
    with pytest.raises(UnsafeSqlError, match="only access the events table"):
        ReadOnlySqlGuard.validate("SELECT * FROM users")

    with pytest.raises(UnsafeSqlError, match="only access the events table"):
        ReadOnlySqlGuard.validate("SELECT * FROM user_turns")

    with pytest.raises(UnsafeSqlError, match="only access the events table"):
        ReadOnlySqlGuard.validate("SELECT * FROM information_schema.tables")


def test_execute_readonly_uses_readonly_pool() -> None:
    class Connection:
        async def fetch(self, query: str, *args: object, **kwargs: object) -> list[dict[str, str]]:
            assert query == "SELECT title FROM events"
            return [{"title": "Market"}]

    class Context:
        async def __aenter__(self) -> Connection:
            return Connection()

        async def __aexit__(self, *_: object) -> None:
            return None

    class Pool:
        def acquire(self) -> Context:
            return Context()

    async def run() -> None:
        assert await execute_readonly(Pool(), "SELECT title FROM events") == [{"title": "Market"}]

    asyncio.run(run())


def test_execute_readonly_returns_json_safe_database_values() -> None:
    class Connection:
        async def fetch(self, query: str, *args: object, **kwargs: object) -> list[dict[str, object]]:
            return [{
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "created_at": datetime(2026, 9, 9, tzinfo=timezone.utc),
            }]

    class Context:
        async def __aenter__(self) -> Connection:
            return Connection()

        async def __aexit__(self, *_: object) -> None:
            return None

    class Pool:
        def acquire(self) -> Context:
            return Context()

    async def run() -> None:
        assert await execute_readonly(Pool(), "SELECT id, created_at FROM events") == [{
            "id": "00000000-0000-0000-0000-000000000001",
            "created_at": "2026-09-09T00:00:00+00:00",
        }]

    asyncio.run(run())
