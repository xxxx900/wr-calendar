from datetime import datetime, timezone

import pytest

from app.core.security import (
    PIIRejectedError,
    PIISanitizer,
    build_idempotency_hash,
    normalize_question,
)


UTC_HOUR = datetime(2026, 9, 5, 14, 20, tzinfo=timezone.utc)


def test_idempotency_hash_is_stable_for_normalized_question() -> None:
    first = build_idempotency_hash("user-1", "  What events are today? ", UTC_HOUR)
    second = build_idempotency_hash("user-1", "what events are today?", UTC_HOUR)

    assert first == second
    assert len(first) == 64


def test_normalize_question_trims_and_lowercases() -> None:
    assert normalize_question("  Hello WORLD  ") == "hello world"


@pytest.mark.parametrize(
    "value",
    [
        "My SSN is 123-45-6789",
        "Email me at person@example.com",
        "Call 555-123-4567",
        "Card 4111 1111 1111 1111",
    ],
)
def test_pii_sanitizer_rejects_high_risk_values(value: str) -> None:
    with pytest.raises(PIIRejectedError):
        PIISanitizer.reject_if_high_risk(value)


def test_pii_sanitizer_accepts_normal_questions() -> None:
    PIISanitizer.reject_if_high_risk("What family events are happening this weekend?")
