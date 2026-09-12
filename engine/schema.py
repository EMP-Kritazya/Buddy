"""Wire contracts. The extension owns this shape; the backend only validates it."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EndReason = Literal[
    "tab_switch", "navigation", "tab_closed", "window_blur", "idle", "locked",
    "paused", "system_sleep", "startup_recovery", "heartbeat",
]


class Client(BaseModel):
    ext_version: str
    device_id: str


class SessionRecord(BaseModel):
    session_id: str
    start_ts: datetime
    end_ts: datetime
    duration_s: float = Field(ge=0)

    # Sensor identity. Browser rows fill the browser block; a future desktop watcher fills
    # app_name/window_title instead, and both live in the same store.
    app_name: str | None = None
    app_type: str | None = None
    window_title: str = ""

    browser_name: str | None = None
    tab_id: int | None = None
    domain: str | None = None
    title: str | None = None
    url_path: str | None = None

    end_reason: EndReason
    is_final: bool
    audible: bool = False
    tz_offset_min: int
    client: Client


class IngestBatch(BaseModel):
    records: list[SessionRecord] = Field(max_length=1000)
