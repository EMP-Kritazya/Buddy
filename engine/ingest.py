from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from engine.schema import IngestBatch

log = logging.getLogger("uvicorn.error")
router = APIRouter()


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


@router.post("/ingest")
def ingest(batch: IngestBatch, request: Request) -> dict:
    store = request.app.state.store
    scorer = request.app.state.scorer

    rows = [r.model_dump(mode="json") for r in batch.records]
    needs_score = store.append_sessions(rows)

    for row in needs_score:
        result = {**scorer.score(row), "from_final": bool(row.get("is_final"))}
        store.save_score(row["session_id"], result)
        log.info(
            "%s %-26s %8s  p=%.2f %-13s %s",
            "final" if row["is_final"] else "live ",
            row.get("domain") or row.get("app_name") or "?",
            _fmt(row["duration_s"]),
            result["p"],
            result["label"],
            (row.get("title") or row.get("window_title") or "")[:48],
        )
    return {"accepted": len(rows), "scored": len(needs_score)}
