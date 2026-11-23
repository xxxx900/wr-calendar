import asyncio
import json

from app.modules.chat.repository import persist_turn


class FakeConnection:
    def __init__(self) -> None:
        self.query = ""
        self.parameters: tuple[object, ...] = ()

    async def fetchval(self, query: str, *parameters: object) -> str:
        self.query = query
        self.parameters = parameters
        return "turn-1"


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


def test_persist_turn_serializes_payload_for_jsonb() -> None:
    connection = FakeConnection()
    payload = {
        "answer": "Saturday market",
        "events": [{"title": "Market"}],
        "generated_sql": "SELECT title FROM events",
    }

    turn_id = asyncio.run(
        persist_turn(FakePool(connection), "user-1", "What is happening?", "hash-1", payload)
    )

    assert turn_id == "turn-1"
    assert "$5::jsonb" in connection.query
    assert connection.parameters[2] == "SELECT title FROM events"
    assert json.loads(connection.parameters[4]) == payload
