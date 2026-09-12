"""The engine loop: the only component that decides when Buddy speaks.

It runs on its own clock (every TICK_SECONDS) because "how is the day going" is a question about
a time window, not about any single record. Ingest never calls this, and this never blocks
ingest.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from engine import config
from engine.store import Store, now, parse_ts

log = logging.getLogger("uvicorn.error")


@dataclass
class EngineState:
    score: float | None = None        # 0-1, time-weighted productivity in the window
    tracked_s: float = 0.0            # seconds of activity we actually observed
    streak_s: float = 0.0             # off-task seconds since the last productive session
    present: bool = False             # is the user even in the browser right now
    top: list[dict] = field(default_factory=list)
    last_tick: str | None = None
    last_checkin: str | None = None
    holding_because: str = "starting up"
    speaking: bool = False

    def as_dict(self) -> dict:
        return {**self.__dict__}


def evaluate(store: Store, at: datetime) -> EngineState:
    """Pure: look at the window and describe it. Makes the decision testable without a clock."""
    window_start = at - timedelta(minutes=config.WINDOW_MINUTES)
    rows = store.scored_since(window_start)

    tracked = productive_s = 0.0
    per_domain: dict[str, float] = {}
    last_productive_end = None

    for row in rows:
        start = max(parse_ts(row["start_ts"]), window_start)
        end = min(parse_ts(row["end_ts"]), at)
        clipped = max((end - start).total_seconds(), 0.0)
        if clipped <= 0:
            continue
        p = row["p"] if row.get("p") is not None else 0.5
        tracked += clipped
        productive_s += clipped * p
        key = row.get("domain") or row.get("app_name") or "unknown"
        per_domain[key] = per_domain.get(key, 0.0) + clipped
        if p >= config.PRODUCTIVE_AT:
            end_ts = parse_ts(row["end_ts"])
            last_productive_end = max(last_productive_end or end_ts, end_ts)

    # The streak counts OFF-TASK TIME WE OBSERVED, not wall-clock. Stepping away from the
    # browser must not inflate it - silence is not evidence of slacking.
    streak = 0.0
    for row in rows:
        end_ts = parse_ts(row["end_ts"])
        if last_productive_end and end_ts <= last_productive_end:
            continue
        p = row["p"] if row.get("p") is not None else 0.5
        if p < config.PRODUCTIVE_AT:
            streak += min((end_ts - max(parse_ts(row["start_ts"]), window_start)).total_seconds(),
                          config.WINDOW_MINUTES * 60)

    last_activity = store.last_activity_at()
    present = bool(last_activity and (at - last_activity).total_seconds() <= config.PRESENCE_TIMEOUT_S)
    last_checkin = store.last_checkin_at()

    return EngineState(
        score=round(productive_s / tracked, 3) if tracked else None,
        tracked_s=round(tracked, 1),
        streak_s=round(streak, 1),
        present=present,
        top=[{"name": k, "seconds": round(v, 1)}
             for k, v in sorted(per_domain.items(), key=lambda kv: -kv[1])[:5]],
        last_tick=at.isoformat(),
        last_checkin=last_checkin.isoformat() if last_checkin else None,
    )


def should_speak(state: EngineState, last_checkin: datetime | None, at: datetime) -> tuple[bool, str]:
    if not state.present:
        return False, "user is not in the browser"
    if state.tracked_s < config.MIN_TRACKED_SECONDS:
        return False, f"only {state.tracked_s:.0f}s of data"
    if last_checkin and (at - last_checkin).total_seconds() < config.COOLDOWN_SECONDS:
        left = config.COOLDOWN_SECONDS - (at - last_checkin).total_seconds()
        return False, f"cooldown {left:.0f}s"
    if state.score is None or state.score >= config.SCORE_THRESHOLD:
        return False, f"score {state.score} is fine"
    if state.streak_s < config.STREAK_SECONDS:
        return False, f"off-task {state.streak_s:.0f}s of {config.STREAK_SECONDS:.0f}s"
    return True, f"score {state.score} with {state.streak_s:.0f}s off task"


async def run_loop(app) -> None:
    """Started by the app's lifespan; cancelled on shutdown."""
    from engine.checkin import run_checkin

    store: Store = app.state.store
    log.info("engine: loop every %ss over a %s-minute window", config.TICK_SECONDS, config.WINDOW_MINUTES)
    while True:
        try:
            at = now()
            state = evaluate(store, at)
            fire, why = should_speak(state, store.last_checkin_at(), at)
            state.holding_because = why
            if fire and not app.state.speaking:
                app.state.speaking = True
                asyncio.create_task(run_checkin(app, state, why))
            state.speaking = app.state.speaking
            app.state.state = state
        except Exception:  # a bad tick must never kill the loop
            log.exception("engine: tick failed")
        await asyncio.sleep(config.TICK_SECONDS)
