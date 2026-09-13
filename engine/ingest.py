"""The sensor's front door: validate, keep the raw row, score it, store it."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from engine import pipeline, rawlog
from engine.schema import IngestBatch

log = logging.getLogger("uvicorn.error")
router = APIRouter()


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


@router.post("/ingest")
async def ingest(batch: IngestBatch, request: Request) -> dict:
    state = request.app.state
    rows = [r.model_dump(mode="json") for r in batch.records]
    rawlog.append(rows)  # the local audit trail, written before anything can fail

    scored = failed = 0
    for row in rows:
        # A row that cannot be scored is not lost - it is already in the raw log and can be
        # replayed. One bad row must not fail the batch: the extension retries a 5xx forever,
        # and the same poisoned batch would block everything queued behind it.
        try:
            record = await pipeline.process(row, state.scorer, state.keeper, state.pool,
                                            state.counted)
        except Exception:
            failed += 1
            log.exception("ingest: could not store session %s", row.get("session_id"))
            continue
        if record is None:
            continue  # a heartbeat whose time was already counted
        scored += 1
        log.info(
            "%s %-24s %7s +%-6s p=%.2f %-13s score %.3f -> %-6.3f %s",
            "final" if record["is_final"] else "live ",
            record["domain"] or record["app_name"] or "?",
            _fmt(record["duration_s"]), _fmt(record["counted_s"]),
            record["p"], record["label"], record["score_before"], record["score_after"],
            (record["title"] or "")[:40],
        )
    return {"accepted": len(rows), "scored": scored, "failed": failed,
            "score": round(state.keeper.value, 3)}
