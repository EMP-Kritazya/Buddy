"""
raw row (log) -> clean fields -> text -> model -> productivity score -> TigerData

One activity row per focus session. While a session is still running the same row is updated,
so only the seconds that are new since the last write ever move the score.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from engine import db, matlab
from engine.store_helpers import parse_ts
from ml.extract import fields
from ml.prep import descriptor

# Async donot remove the need for mutual exclusion
_lock = asyncio.Lock()


async def process(row: dict, scorer, keeper, pool, counted_cache: dict) -> dict | None:
    """Score one incoming row, fold it into the running score, upsert it.

    Returns the stored record, or None when the row adds no new time (a repeated or stale
    heartbeat) - in which case the database is not touched at all.
    """
    async with _lock:
        session_id = row["session_id"]
        total = float(row.get("duration_s", 0.0))
        is_final = bool(row.get("is_final"))
        cached = counted_cache.get(session_id)
        already, was_final = cached if cached else (0.0, False)
        counted = max(total - already, 0.0)
        
        if counted <= 0 and cached and (was_final or not is_final):
            return None

        clean = fields(row)
        text = descriptor(row)

        verdict = scorer.score(row)

        end = parse_ts(row["end_ts"])
        target = 1.0 if verdict["label"] == "productive" else 0.0
        update = keeper.apply(target, counted, end)

        record = {
            "session_id": session_id,
            "start_ts": parse_ts(row["start_ts"]),
            "end_ts": end,
            "duration_s": total,
            "tz_offset_min": int(row.get("tz_offset_min") or 0),
            "device_id": (row.get("client") or {}).get("device_id"),
            "app_name": clean["app_name"] or None,
            "app_type": clean["app_type"] or None,
            "domain": clean["domain"] or None,
            "title": clean["title"] or None,
            "model_text": text,
            "p": verdict["p"],
            "label": verdict["label"],
            "model": verdict["source"],
            "score_after": update.after,
            "is_final": is_final,
            "end_reason": row.get("end_reason"),
        }
        stored = await db.upsert_activity(pool, record)
        # trust the database's value: it applies greatest() and is the source of truth
        counted_cache[session_id] = (float(stored), is_final or was_final)

        matlab.notify(end, update.after)
        record["counted_s"] = round(counted, 2)
        record["score_before"] = update.before
        return record


def local_time(end, offset_minutes: int) -> str:
    return (end + timedelta(minutes=offset_minutes)).strftime("%Y-%m-%d %H:%M")
