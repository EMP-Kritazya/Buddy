from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from engine import db, matlab, mentor, voice
from engine.store_helpers import now

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    """Liveness, plus whether the ML is actually doing the judging.

    `using_model` false means every row is being scored by the keyword rules - the engine is up
    and the score still moves, but the classifier is not part of it. `scorer.error` says why.
    """
    stats = request.app.state.scorer.stats()
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetchval("select count(*) from activity")
    return {"ok": True, "using_model": stats["using_model"],
            "score": round(request.app.state.keeper.value, 3),
            "activity_rows": rows, "scorer": stats, "matlab": matlab.state(),
            "mentor": mentor.state(), "voice": voice.state()}


@router.get("/score")
async def score(request: Request) -> dict:
    """The running productivity score, 0-1."""
    return request.app.state.keeper.as_dict()


@router.get("/activity")
async def activity(request: Request, hours: float = Query(8, gt=0, le=168),
                   limit: int = Query(500, ge=1, le=5000)) -> list[dict]:
    """One row per focus session - what Gemini reads to talk about the day."""
    rows = await db.activity_since(request.app.state.pool,
                                   now() - timedelta(hours=hours), limit)
    return [_jsonable(r) for r in rows]


@router.get("/summary")
async def summary(request: Request, hours: float = Query(8, gt=0, le=168)) -> dict:
    """The same window, small enough to put in a prompt."""
    data = await db.summary(request.app.state.pool, now() - timedelta(hours=hours))
    tracked = float(data["totals"]["tracked"] or 0)
    productive = float(data["totals"]["productive"] or 0)
    places = [{"name": p["name"], "minutes": round(float(p["seconds"]) / 60, 1),
               "p": round(float(p["p"]), 3) if p["p"] is not None else None}
              for p in data["places"]]
    return {
        "hours": hours,
        "score_now": round(request.app.state.keeper.value, 3),
        "tracked_minutes": round(tracked / 60, 1),
        "productive_minutes": round(productive / 60, 1),
        "productive_share": round(productive / tracked, 3) if tracked else None,
        "sessions": data["totals"]["sessions"],
        "top_productive": [p for p in places if (p["p"] or 0) >= 0.5][:5],
        "top_distractions": [p for p in places if (p["p"] or 0) < 0.5][:5],
    }


@router.get("/timeline")
async def timeline(request: Request, hours: float = Query(6, gt=0, le=48),
                   bucket_minutes: float = Query(5, gt=0, le=60)) -> list[dict]:
    """Time-weighted productivity per bucket - the series MATLAB plots.

    A session is split across every bucket it spans, so a 30-minute video lowers thirty minutes
    of the line instead of one spike.
    """
    at = now()
    start = at - timedelta(hours=hours)
    size = bucket_minutes * 60
    rows = await db.activity_since(request.app.state.pool, start, 5000)

    buckets: dict[float, list[float]] = {}
    for row in rows:
        s = max(row["start_ts"], start).timestamp()
        e = min(row["end_ts"], at).timestamp()
        p = float(row["p"])
        while s < e:
            key = (s // size) * size
            slice_end = min(e, key + size)
            acc = buckets.setdefault(key, [0.0, 0.0])
            acc[0] += slice_end - s
            acc[1] += (slice_end - s) * p
            s = slice_end

    return [{"ts": datetime.fromtimestamp(k, timezone.utc).isoformat(),
             "tracked_s": round(v[0], 1),
             "productive_fraction": round(v[1] / v[0], 3) if v[0] else None}
            for k, v in sorted(buckets.items())]


class MatlabTarget(BaseModel):
    """Where MATLAB is reachable right now. The ngrok URL changes; this is how we follow it."""
    url: str
    token: str | None = None


@router.get("/matlab")
async def matlab_state() -> dict:
    """Queue depth, window fill, call count and the last trigger MATLAB returned."""
    return matlab.state()


@router.post("/matlab/url")
async def matlab_url(target: MatlabTarget) -> dict:
    """Repoint the engine at a new tunnel without restarting it, and remember the change."""
    return matlab.configure(url=target.url, token=target.token)


@router.post("/matlab/check")
async def matlab_check() -> dict:
    """Send one synthetic window and report what came back. Run this before demoing."""
    return await matlab.check()


@router.post("/mentor/test")
async def mentor_test(request: Request, level: int = Query(2, ge=1, le=2)) -> dict:
    """Run the nudge pipeline once by hand, bypassing MATLAB and the cooldown.

    The whole chain only fires when you are genuinely unproductive for a while, which is a poor
    way to iterate on a prompt. This runs the same code path on demand.
    """
    from engine.matlab import Trigger
    trigger = Trigger(level=level, reason="manual test", at=now(),
                      score=request.app.state.keeper.value)
    nudge = await mentor.handle(trigger, request.app.state.pool)
    return {"spoke": nudge is not None,
            "text": nudge.text if nudge else None,
            "context_preview": mentor.build_prompt(
                trigger, await mentor.gather_context(trigger, request.app.state.pool))}


@router.post("/model/reload")
async def model_reload(request: Request) -> dict:
    """Pick up a freshly trained model without restarting the engine."""
    return {"model": request.app.state.scorer.load()}


def _jsonable(row: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}
