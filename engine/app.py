"""The local engine: one process, one port.

    uvicorn engine.app:app --host 0.0.0.0 --port 8000

--host 0.0.0.0 is not optional once the ESP32 is involved: uvicorn binds 127.0.0.1 by default,
which is reachable only from this laptop. The device needs the LAN address.

Collect logs -> clean and prep -> run the model -> update the productivity score -> store one
row per focus session in TigerData.
"""

from __future__ import annotations

import contextlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine import api, config, db, goals, ingest, matlab, mentor, reminders, voice, web
from engine.score import ScoreKeeper
from engine.scoring import Scorer

log = logging.getLogger("uvicorn.error")

# .env is loaded by engine.config at import time - see the note there for why it cannot be done
# from this file.


def lan_address() -> str:
    """This machine's address on the LAN - what the watch firmware must be flashed with.

    Opening a UDP socket to an outside address makes the OS pick the interface it would really
    route through, which is the one the ESP32 shares. No packet is sent. Reading hostname or
    127.0.0.1 would give an address the device cannot reach.
    """
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.scorer = Scorer()
    app.state.keeper = ScoreKeeper()
    app.state.pool = await db.connect()

    # Resume where the last run left off: the score rides on the newest activity row, and the
    # durations tell us how much of each recent session has already been counted.
    score, counted = await db.load_state(app.state.pool)
    app.state.keeper.resume_from(score)
    app.state.counted = counted
    log.info("engine: model=%s score=%.3f resuming %d recent sessions",
             app.state.scorer.version, app.state.keeper.value, len(counted))
    log.info("engine: watch should use  SERVER = \"http://%s:8000\"", lan_address())
    reminders.start(app.state.pool)
    matlab.start()
    matlab.prime(await db.recent_scores(app.state.pool, config.MATLAB_WINDOW))
    # A trigger MATLAB raises now has somewhere to go: gather context -> Gemini -> speak.
    matlab.set_handler(mentor.make_handler(app.state.pool))
    mentor.prime(await db.recent_conversation(app.state.pool, mentor.HISTORY_TURNS * 2))
    if app.state.scorer.pipeline is None:
        log.warning("engine: NO MODEL - every row will be scored by ml/rules.py (%s)",
                    app.state.scorer.error)
    try:
        yield
    finally:
        await reminders.stop()
        await matlab.stop()
        await app.state.pool.close()


app = FastAPI(title="Buddy engine", lifespan=lifespan)

# The dashboard runs on its own dev server, so its fetches are cross-origin. Only localhost is
# allowed: the engine binds 0.0.0.0 for the watch, and this keeps a page on the same Wi-Fi from
# reading someone's activity just because it can reach the port.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ingest.router)
app.include_router(api.router)
app.include_router(goals.router)
app.include_router(voice.router)
app.include_router(voice.device)   # /pending-speech, /voice, /audio - the watch's contract
app.include_router(web.router)     # /api/* - the dashboard's contract
