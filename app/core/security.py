from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


class PIIRejectedError(ValueError):
    """Raised when a question contains high-risk personally identifiable information."""


class PIISanitizer:
    _patterns = (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.IGNORECASE),
        re.compile(r"(?<!\d)(?:\+?1[ -.]?)?(?:\(?\d{3}\)?[ -.]?)\d{3}[ -.]?\d{4}(?!\d)"),
    )

    @classmethod
    def contains_high_risk_pii(cls, value: str) -> bool:
        return any(pattern.search(value) for pattern in cls._patterns)

    @classmethod
    def reject_if_high_risk(cls, value: str) -> None:
        if cls.contains_high_risk_pii(value):
            raise PIIRejectedError("Question contains sensitive personal information.")


def normalize_question(raw_question: str) -> str:
    return raw_question.strip().lower()


def current_utc_hour(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d-%H")


def build_idempotency_hash(user_id: str, raw_question: str, value: datetime | None = None) -> str:
    material = f"{user_id}:{normalize_question(raw_question)}:{current_utc_hour(value)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
