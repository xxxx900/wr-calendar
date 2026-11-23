from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.calendar.vision import OpenAICalendarVision


def _create_minimal_pdf_bytes() -> bytes:
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PDF")
        return buf.getvalue()
    except Exception:
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 100 100]/Parent 2 0 R>>endobj xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"


def test_prepare_image_urls_for_regular_image() -> None:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    urls = OpenAICalendarVision._prepare_image_urls(png_bytes)
    assert len(urls) == 1
    assert urls[0]["type"] == "image_url"
    assert urls[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_prepare_image_urls_for_pdf_document() -> None:
    pytest.importorskip("pypdfium2")
    pytest.importorskip("PIL")
    pdf_bytes = _create_minimal_pdf_bytes()
    urls = OpenAICalendarVision._prepare_image_urls(pdf_bytes)
    assert len(urls) >= 1
    assert urls[0]["type"] == "image_url"
    assert urls[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_prepare_image_urls_rejects_corrupted_pdf() -> None:
    pytest.importorskip("pypdfium2")
    corrupted = b"%PDF-1.4 corrupted content without valid trailer"
    with pytest.raises(ValueError, match="Failed to process PDF document"):
        OpenAICalendarVision._prepare_image_urls(corrupted)


def test_vision_call_with_pdf_sends_pages_to_openai() -> None:
    pytest.importorskip("pypdfium2")
    pytest.importorskip("PIL")
    import asyncio

    vision = OpenAICalendarVision(api_key="fake-key")
    pdf_bytes = _create_minimal_pdf_bytes()

    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(message=AsyncMock(content='{"events": [{"title": "Pool Party", "event_date": "2026-09-15"}]}'))
    ]

    async def run() -> None:
        with patch.object(vision._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)) as mock_create:
            events = await vision(pdf_bytes)
            assert len(events) == 1
            assert events[0]["title"] == "Pool Party"
            mock_create.assert_awaited_once()
            call_kwargs = mock_create.call_args.kwargs
            messages = call_kwargs["messages"]
            user_content = messages[1]["content"]
            assert any(part.get("type") == "image_url" for part in user_content)

    asyncio.run(run())
