from __future__ import annotations

import json
from typing import Any

import httpx


class UpstashRedisClient:
    def __init__(self, url: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

    async def _command(self, *arguments: object) -> Any:
        response = await self._client.post("/", json=list(arguments))
        response.raise_for_status()
        return response.json()["result"]

    async def get(self, key: str) -> Any:
        value = await self._command("GET", key)
        return None if value is None else json.loads(value)

    async def set(
        self,
        key: str,
        value: Any,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> Any:
        arguments: list[object] = ["SET", key, json.dumps(value)]
        if ex is not None:
            arguments.extend(["EX", ex])
        if nx:
            arguments.append("NX")
        return await self._command(*arguments)

    async def incr(self, key: str) -> int:
        return int(await self._command("INCR", key))

    async def zadd(self, key: str, score: float, member: str) -> int:
        return int(await self._command("ZADD", key, score, member))

    async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        return int(await self._command("ZREMRANGEBYSCORE", key, minimum, maximum))

    async def zcard(self, key: str) -> int:
        return int(await self._command("ZCARD", key))

    async def zrange(self, key: str, start: int, stop: int) -> list[str]:
        return list(await self._command("ZRANGE", key, start, stop))

    async def zrem(self, key: str, member: str) -> int:
        return int(await self._command("ZREM", key, member))

    async def expire(self, key: str, seconds: int) -> Any:
        return await self._command("EXPIRE", key, seconds)

    async def delete(self, key: str) -> Any:
        return await self._command("DEL", key)

    async def close(self) -> None:
        await self._client.aclose()


def create_redis_client(url: str, token: str) -> UpstashRedisClient:
    return UpstashRedisClient(url, token)
