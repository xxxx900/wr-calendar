from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sse_starlette.sse import ServerSentEvent


@dataclass(frozen=True)
class IngestionEvent:
    event: str
    data: dict[str, Any]


ProcessUpload = Callable[[bytes, asyncio.Queue[IngestionEvent]], Awaitable[dict[str, int]]]


async def stream_calendar_ingestion(
    image_bytes: bytes,
    process_upload: ProcessUpload,
) -> AsyncIterator[ServerSentEvent]:
    queue: asyncio.Queue[IngestionEvent] = asyncio.Queue()
    worker = asyncio.create_task(process_upload(image_bytes, queue))

    try:
        await queue.put(IngestionEvent("status", {"stage": "upload_received", "pct": 10}))
        while not worker.done() or not queue.empty():
            try:
                message = await asyncio.wait_for(queue.get(), timeout=5)
            except asyncio.TimeoutError:
                yield ServerSentEvent(comment="ping")
                continue

            yield ServerSentEvent(event=message.event, data=json.dumps(message.data))

        result = worker.result()
        yield ServerSentEvent(event="complete", data=json.dumps(result))
    except asyncio.CancelledError:
        worker.cancel()
        raise
    except Exception as exc:
        if not worker.done():
            worker.cancel()
        yield ServerSentEvent(event="error", data={"detail": str(exc)})
    finally:
        if not worker.done():
            worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


async def process_calendar_upload(
    image_bytes: bytes,
    queue: asyncio.Queue[IngestionEvent],
    vision_ocr: Callable[[bytes], Awaitable[list[dict[str, Any]]]],
    upsert_events: Callable[[list[dict[str, Any]]], Awaitable[dict[str, int]]],
) -> dict[str, int]:
    await queue.put(IngestionEvent("status", {"stage": "vision_ocr_processing", "pct": 40}))
    extracted_events = await vision_ocr(image_bytes)
    await queue.put(IngestionEvent("status", {"stage": "parsing_and_validating", "pct": 75}))
    validated_events = [event for event in extracted_events if event.get("title")]
    await queue.put(IngestionEvent("status", {"stage": "database_upsert", "pct": 90}))
    return await upsert_events(validated_events)


async def extract_calendar_events(
    image_bytes: bytes,
    vision_ocr: Callable[[bytes], Awaitable[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    extracted_events = await vision_ocr(image_bytes)
    return [event for event in extracted_events if event.get("title")]
