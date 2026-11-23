import asyncio
import json

from app.modules.calendar.service import IngestionEvent, stream_calendar_ingestion


def test_calendar_stream_emits_progress_and_completion() -> None:
    async def process_upload(image: bytes, queue: asyncio.Queue[IngestionEvent]) -> dict[str, int]:
        await queue.put(IngestionEvent("status", {"stage": "vision_ocr_processing", "pct": 40}))
        return {"inserted": 2, "updated": 1}

    async def run() -> list[object]:
        return [event async for event in stream_calendar_ingestion(b"image", process_upload)]

    events = asyncio.run(run())
    assert [event.event for event in events] == ["status", "status", "complete"]
    assert json.loads(events[-1].data) == {"inserted": 2, "updated": 1}
