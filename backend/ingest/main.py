"""
Buddy ingest stub: receives focus sessions from the Chrome extension (as for now).

Records are appended to sessions.jsonl for now; need to plug in the classifier and the TigerData upsert here later. Heartbeat (non-final) rows and the final row share a session_id, and the latest one wins.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

DATA_FILE = Path(__file__).with_name("sessions.jsonl")

EndReason = Literal[
    "tab_switch",
    "navigation",
    "tab_closed",
    "window_blur",
    "idle",
    "locked",
    "paused",
    "system_sleep",
    "startup_recovery",
    "heartbeat",
]


class Client(BaseModel):
    ext_version: str
    device_id: str


class SessionRecord(BaseModel):
    session_id: str
    start_ts: datetime
    end_ts: datetime
    duration_s: float = Field(ge=0)

    # For application - later
    app_name: str | None = None
    app_type: str | None = None
    window_title: str = ""

    # Browser info
    browser_name: str | None = None
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


log = logging.getLogger("uvicorn.error")
app = FastAPI(title="Buddy ingest")


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


@app.post("/ingest")
def ingest(batch: IngestBatch) -> dict:
    with DATA_FILE.open("a", encoding="utf-8") as f:
        for r in batch.records:
            f.write(r.model_dump_json() + "\n")
    for r in batch.records:
        kind = "final" if r.is_final else "live "
        log.info(
            "%s %-24s %8s  %-16s %s",
            kind, r.domain or r.app_name, _fmt_duration(r.duration_s), r.end_reason,
            (r.title or r.window_title)[:60],
        )
    return {"accepted": len(batch.records)}


@app.get("/sessions")
def sessions(limit: int = Query(50, ge=1, le=1000)) -> list[dict]:
    """Latest snapshot per session, newest first: the view the TigerData upsert will produce."""
    if not DATA_FILE.exists():
        return []
    latest: dict[str, dict] = {}
    with DATA_FILE.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            latest[rec["session_id"]] = rec
    return sorted(latest.values(), key=lambda r: r["start_ts"], reverse=True)[:limit]


@app.get("/health")
def health() -> dict:
    return {"ok": True}
