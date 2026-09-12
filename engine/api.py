"""Read-side API: what the popup, the dashboard and MATLAB ask for."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query, Request

from engine import config, speaker
from engine.checkin import run_checkin
from engine.store import now, parse_ts

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    return {"ok": True, "model": request.app.state.scorer.version,
            **request.app.state.store.counts()}


@router.get("/state")
def state(request: Request) -> dict:
    """Everything the engine currently believes. Drives the popup and the dashboard."""
    s = request.app.state.state
    return {**s.as_dict(), "thresholds": {
        "score": config.SCORE_THRESHOLD, "streak_s": config.STREAK_SECONDS,
        "cooldown_s": config.COOLDOWN_SECONDS, "window_min": config.WINDOW_MINUTES}}


@router.get("/timeline")
def timeline(
    request: Request,
    hours: float = Query(6, gt=0, le=48),
    bucket_minutes: float = Query(5, gt=0, le=60),
) -> list[dict]:
    """Time-weighted productivity per bucket - the series MATLAB plots.

    A session is split across every bucket it spans, so a 30-minute video lowers thirty
    minutes of the line instead of one spike.
    """
    at = now()
    start = at - timedelta(hours=hours)
    size = bucket_minutes * 60
    buckets: dict[float, list[float]] = {}

    for row in request.app.state.store.scored_since(start):
        s = max(parse_ts(row["start_ts"]), start).timestamp()
        e = min(parse_ts(row["end_ts"]), at).timestamp()
        p = row["p"] if row.get("p") is not None else 0.5
        while s < e:
            key = (s // size) * size
            slice_end = min(e, key + size)
            seconds = slice_end - s
            acc = buckets.setdefault(key, [0.0, 0.0])
            acc[0] += seconds
            acc[1] += seconds * p
            s = slice_end

    from datetime import datetime, timezone
    return [
        {"ts": datetime.fromtimestamp(k, timezone.utc).isoformat(),
         "tracked_s": round(v[0], 1),
         "productive_fraction": round(v[1] / v[0], 3) if v[0] else None}
        for k, v in sorted(buckets.items())
    ]


@router.get("/stats")
def stats(request: Request, hours: float = Query(24, gt=0, le=168)) -> dict:
    at = now()
    rows = request.app.state.store.scored_since(at - timedelta(hours=hours))
    per: dict[str, dict] = {}
    tracked = productive = 0.0
    for row in rows:
        seconds = float(row["duration_s"])
        p = row["p"] if row.get("p") is not None else 0.5
        tracked += seconds
        productive += seconds * p
        key = row.get("domain") or row.get("app_name") or "unknown"
        entry = per.setdefault(key, {"seconds": 0.0, "p_sum": 0.0})
        entry["seconds"] += seconds
        entry["p_sum"] += seconds * p
    return {
        "hours": hours,
        "tracked_s": round(tracked, 1),
        "productivity": round(productive / tracked, 3) if tracked else None,
        "by_domain": sorted(
            ({"name": k, "seconds": round(v["seconds"], 1),
              "p": round(v["p_sum"] / v["seconds"], 3) if v["seconds"] else None}
             for k, v in per.items()),
            key=lambda d: -d["seconds"],
        )[:20],
    }


@router.post("/checkin/now")
async def checkin_now(request: Request) -> dict:
    """The demo button: speak right now, ignoring thresholds and cooldown."""
    return await run_checkin(request.app, request.app.state.state, "manual")


@router.get("/speak/pending")
def speak_pending() -> dict:
    """The ESP32 polls this. Returns the next thing to say, or nothing."""
    item = speaker.take_pending()
    return item or {"text": None}


@router.post("/model/reload")
def model_reload(request: Request) -> dict:
    """Pick up a freshly trained model without restarting the engine."""
    return {"model": request.app.state.scorer.load()}
