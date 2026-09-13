"""Timestamp helpers shared by the pipeline and the API."""
from __future__ import annotations

from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
