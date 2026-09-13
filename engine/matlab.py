from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable

from engine.config import (DATA_DIR, MATLAB_COOLDOWN_S, MATLAB_ENABLED, MATLAB_FUNCTION,
                           MATLAB_HARD_COOLDOWN_S, MATLAB_QUEUE_MAX, MATLAB_TIMEOUT_S,
                           MATLAB_TOKEN, MATLAB_URL, MATLAB_VERIFY_TLS, MATLAB_WINDOW)

log = logging.getLogger("uvicorn.error")

SOFT, HARD = 1, 2
HANDLER_TIMEOUT_S = 30.0   # ceiling on one Gemini + speak round trip


class MatlabError(RuntimeError):
    """A call that reached the network but did not come back as a usable answer."""


@dataclass(frozen=True)
class Trigger:
    level: int      # 0 fine, 1 soft nudge, 2 hard nudge
    reason: str     # MATLAB's own words, worth passing to Gemini verbatim
    at: datetime
    score: float


# The tunnel in front of MATLAB is an ngrok free-tier URL, which changes every time it is
# restarted. Waiting on a redeploy to pick up a new one is not an option mid-demo, so the
# address is runtime state, not a constant: POST /matlab/url replaces it in place, and the
# override is written here so it also survives an engine restart.
OVERRIDE_FILE = DATA_DIR / "matlab.json"

_url = MATLAB_URL
_token = MATLAB_TOKEN


def configure(url: str | None = None, token: str | None = None, persist: bool = True) -> dict:
    """Point the engine at a different MATLAB, without a restart. Starts the worker if needed."""
    global _url, _token
    if url is not None:
        _url = url.rstrip("/")
    if token is not None:
        _token = token
    if persist:
        with contextlib.suppress(OSError):
            OVERRIDE_FILE.write_text(json.dumps({"url": _url, "token": _token}))
    log.info("matlab: url set to %s", _url or "(none)")
    if _url and (_worker is None or _worker.done()):
        start()
    return state()


def _load_override() -> None:
    """A URL set at runtime outranks the one in .env - it is the more recent decision."""
    global _url, _token
    with contextlib.suppress(OSError, ValueError):
        saved = json.loads(OVERRIDE_FILE.read_text())
        _url = saved.get("url") or _url
        _token = saved.get("token") or _token
        log.info("matlab: using saved url %s", _url)


# --- state -------------------------------------------------------------------------------
# The queue is the handoff between the ingest path (producer) and the single worker (consumer).
_queue: asyncio.Queue[tuple[float, float]] | None = None
_worker: asyncio.Task | None = None
# Owned by the worker alone, so no lock is needed: the last MATLAB_WINDOW points, oldest first.
_points: deque[tuple[float, float]] = deque(maxlen=MATLAB_WINDOW)

_sent = 0
_dropped = 0
_last: Trigger | None = None   # what MATLAB said most recently, trigger or not
_spoke_at = 0.0                # monotonic clock of the last trigger we acted on
_spoke_level = 0               # and how loud it was

# Where a trigger goes next. Gemini will register here; until then a trigger just gets logged.
Handler = Callable[[Trigger], Awaitable[None]]
_handler: Handler | None = None


def set_handler(fn: Handler) -> None:
    global _handler
    _handler = fn


# --- lifecycle ---------------------------------------------------------------------------

def start() -> None:
    """Open the queue and start the worker. Called once from the app lifespan."""
    global _queue, _worker
    _load_override()
    if not MATLAB_ENABLED:
        log.info("matlab: disabled (BUDDY_MATLAB_ENABLED=0)")
        return
    if not _url:
        log.info("matlab: no URL yet - POST /matlab/url to set one")
        return
    _queue = asyncio.Queue(maxsize=MATLAB_QUEUE_MAX)
    _worker = asyncio.create_task(_run(), name="matlab-worker")
    log.info("matlab: worker started, window=%d cooldown=%.0fs soft / %.0fs hard",
             MATLAB_WINDOW, MATLAB_COOLDOWN_S, MATLAB_HARD_COOLDOWN_S)


async def stop(timeout: float = 5.0) -> None:
    """Let the backlog finish, then shut the worker down cleanly."""
    if _worker is None or _queue is None:
        return
    try:
        await asyncio.wait_for(_queue.join(), timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("matlab: %d point(s) still queued at shutdown", _queue.qsize())
    _worker.cancel()
    try:
        await _worker
    except asyncio.CancelledError:
        pass


def prime(points: list[tuple[float, float]]) -> None:
    """Fill the window from history so the first live point can produce a call immediately."""
    _points.clear()
    _points.extend(points[-MATLAB_WINDOW:])
    if _points:
        log.info("matlab: primed %d/%d points from history", len(_points), MATLAB_WINDOW)


# --- producer ----------------------------------------------------------------------------

def notify(ts: datetime, score: float) -> None:
    """Hand one point to the worker. Called from the ingest path: never blocks, never raises."""
    global _dropped
    if _queue is None:
        return
    point = (ts.timestamp(), float(score))
    try:
        _queue.put_nowait(point)
    except asyncio.QueueFull:
        # MATLAB is wedged. Keep the freshest points: for trigger detection a stale sample is
        # worth less than a new one, and the full history is in the database regardless.
        _dropped += 1
        try:
            _queue.get_nowait()
            _queue.task_done()
        except asyncio.QueueEmpty:
            pass
        try:
            _queue.put_nowait(point)
        except asyncio.QueueFull:
            pass
        if _dropped % 50 == 1:
            log.warning("matlab: queue full, dropped %d point(s) so far", _dropped)


# --- consumer ----------------------------------------------------------------------------

async def _run() -> None:
    """Drain the queue forever, one point at a time.

    Sequential by construction: one call in flight at a time, so triggers arrive in the order
    the activity happened. Every iteration is guarded - one bad response must not end the loop
    and leave the queue filling silently behind a dead worker.
    """
    assert _queue is not None
    while True:
        point = await _queue.get()
        try:
            await _handle_point(point)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("matlab: call failed (%s: %s)", type(exc).__name__, exc)
        finally:
            _queue.task_done()


async def _handle_point(point: tuple[float, float]) -> None:
    global _sent, _last
    _points.append(point)
    # Send immediately, with whatever history we have. The deque caps the window at
    # MATLAB_WINDOW; it never gates on it. MATLAB can look at numel(scores) if a short window
    # is not enough for its algorithm - that call belongs on its side, not here.
    trigger = await evaluate(list(_points))
    _sent += 1
    _last = trigger

    # Every signal is printed, including 0 - a quiet run should look quiet, not look broken.
    _print(trigger)
    if trigger.level == 0:
        return
    if _handler is None or not _may_speak(trigger):
        return
    # The handler talks to Gemini and ElevenLabs - both are network calls that can hang. A
    # stalled handler would stall the whole queue behind it, so it gets a hard ceiling.
    try:
        await asyncio.wait_for(_handler(trigger), timeout=HANDLER_TIMEOUT_S)
    except asyncio.TimeoutError:
        log.warning("matlab: handler exceeded %.0fs, abandoned", HANDLER_TIMEOUT_S)
    except Exception as exc:
        log.warning("matlab: trigger handler failed (%s: %s)", type(exc).__name__, exc)


async def evaluate(window: list[tuple[float, float]]) -> Trigger:
    """POST one window to MATLAB and read the trigger back out. Raises MatlabError on a bad reply.

    The payload shape is MATLAB Production Server's RESTful API: positional arguments in `rhs`,
    return values in `lhs`. nargout=2 because analyze_scores returns (trigger, reason).
    """
    import httpx

    timestamps = [t for t, _ in window]
    scores = [s for _, s in window]
    payload = {
        "nargout": 2,
        "rhs": [
            {"mwtype": "double", "mwdata": scores},
            {"mwtype": "double", "mwdata": timestamps},
        ],
    }
    async with httpx.AsyncClient(timeout=MATLAB_TIMEOUT_S, verify=MATLAB_VERIFY_TLS) as client:
        r = await client.post(f"{_url}/{MATLAB_FUNCTION}", json=payload,
                              headers={"mwRESTPersonalAccessToken": _token})

    if r.status_code != 200:
        raise MatlabError(f"HTTP {r.status_code} from {_url} - tunnel down or URL rotated?")
    try:
        data = r.json()
    except ValueError:
        raise MatlabError(f"expected JSON, got: {r.text[:80]}".replace("\n", " ")) from None
    if "error" in data:
        raise MatlabError(str(data["error"].get("message")))

    try:
        lhs = data["lhs"]
    except (KeyError, TypeError):
        raise MatlabError(f"no 'lhs' in reply: {str(data)[:80]}") from None
    return Trigger(
        level=int(lhs[0]["mwdata"][0]),
        reason=_text(lhs[1]["mwdata"]),
        at=datetime.fromtimestamp(window[-1][0]).astimezone(),
        score=window[-1][1],
    )


def _text(mwdata) -> str:
    """MATLAB char arrays come back as a list of single characters; scalars come back plain."""
    if isinstance(mwdata, list):
        return "".join(str(c) for c in mwdata)
    return str(mwdata)


LEVELS = {0: "0 OK  ", SOFT: "1 SOFT", HARD: "2 HARD"}


def _print(trigger: Trigger) -> None:
    """One line per MATLAB answer, in the same shape as the ingest lines above it."""
    name = LEVELS.get(trigger.level, f"{trigger.level} ?")
    line = f"matlab {name}  score={trigger.score:.2f}  {trigger.reason}"
    # Display only. Gemini is NOT called from here - this runs on every answer, including the
    # ones suppressed by the cooldown. The handler in _handle_point() is the dispatch point.
    if trigger.level == 0:
        log.info(line)
    else:
        log.warning("*** %s ***", line)



def _may_speak(trigger: Trigger) -> bool:
    """Rate-limit Buddy's voice, not MATLAB's opinion.

    A slump produces a trigger on every call for as long as it lasts, so acting on each one
    would have Buddy talking every few seconds - the exact nagging this is meant to avoid.

    The quiet period depends on how bad things are, not on what was said last. A hard trigger
    means the score is already below 0.5, so it is held to MATLAB_HARD_COOLDOWN_S rather than
    serving out a longer silence a soft nudge earned. And a hard trigger always breaks through a
    cooldown started by a soft one: things got worse, which is the whole point of saying it.
    """
    global _spoke_at, _spoke_level
    now = asyncio.get_event_loop().time()
    quiet_for = now - _spoke_at
    cooldown = MATLAB_HARD_COOLDOWN_S if trigger.level == HARD else MATLAB_COOLDOWN_S
    escalated = trigger.level == HARD and _spoke_level == SOFT
    if quiet_for < cooldown and not escalated:
        log.info("matlab: suppressed %s, %.0fs of %.0fs cooldown left",
                 "hard" if trigger.level == HARD else "soft", cooldown - quiet_for, cooldown)
        return False
    _spoke_at, _spoke_level = now, trigger.level
    return True


async def check() -> dict:
    """Send one synthetic window and report exactly what came back.

    The point of this is the demo: the tunnel is the most fragile link in the chain, and
    "is it up?" should be one request away rather than something you learn from the logs
    twenty minutes into a session.
    """
    if not _url:
        return {"ok": False, "error": "no URL set - POST /matlab/url first"}
    now = asyncio.get_event_loop().time()
    window = [(now + i, 0.5) for i in range(MATLAB_WINDOW)]
    try:
        trigger = await evaluate(window)
    except MatlabError as exc:
        return {"ok": False, "url": _url, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "url": _url, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "url": _url,
            "trigger": {"level": trigger.level, "reason": trigger.reason}}


def state() -> dict:
    """What /health reports, so the loop is visible without reading logs."""
    return {
        "enabled": bool(MATLAB_ENABLED and _url),
        "url": _url or None,
        "running": bool(_worker and not _worker.done()),
        "queued": 0 if _queue is None else _queue.qsize(),
        "window": f"{len(_points)}/{MATLAB_WINDOW}",   # points sent per call, capped
        "calls": _sent,
        "dropped": _dropped,
        "cooldown_s": {"soft": MATLAB_COOLDOWN_S, "hard": MATLAB_HARD_COOLDOWN_S},
        "last_trigger": None if _last is None else
            {"level": _last.level, "reason": _last.reason, "at": _last.at.isoformat()},
    }
