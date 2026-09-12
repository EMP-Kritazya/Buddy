"""The local engine: one process, one port.

  uvicorn engine.app:app --port 8000

Ingest, scoring, the trigger loop and the read API all live here so the demo needs one command.
The pieces are split by clock, not by convenience: ingest answers in milliseconds, the loop
thinks every 15 seconds, and check-ins take as long as Gemini takes - on a background task.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI

from engine import api, ingest
from engine.scoring import Scorer
from engine.store import Store
from engine.trigger import EngineState, run_loop

log = logging.getLogger("uvicorn.error")

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = Store()
    app.state.scorer = Scorer()
    app.state.state = EngineState()
    app.state.speaking = False
    log.info("engine: %s sessions on disk, model=%s",
             app.state.store.counts()["sessions"], app.state.scorer.version)

    task = asyncio.create_task(run_loop(app))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Buddy engine", lifespan=lifespan)
app.include_router(ingest.router)
app.include_router(api.router)
