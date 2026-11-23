import asyncio
from datetime import datetime, timezone

from app.modules.calendar.repository import fetch_current_month_events


class FakeConnection:
    def __init__(self) -> None:
        self.parameters: tuple[object, ...] | None = None

    async def fetch(self, _query: str, *parameters: object) -> list[dict[str, object]]:
        self.parameters = parameters
        return [{"title": "Community meeting"}]


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *_: object) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def test_fetch_current_month_events_uses_utc_month_bounds() -> None:
    connection = FakeConnection()
    pool = FakePool(connection)

    async def run() -> list[dict[str, object]]:
        return await fetch_current_month_events(
            pool,
            datetime(2026, 12, 15, 23, 30, tzinfo=timezone.utc),
        )

    events = asyncio.run(run())

    assert events[0]["title"] == "Community meeting"
    assert connection.parameters == (
        datetime(2026, 12, 1).date(),
        datetime(2027, 1, 1).date(),
    )