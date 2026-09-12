"""One check-in, start to finish. Runs as a background task so a slow Gemini or TTS call never
delays the loop or the browser."""
from __future__ import annotations

import asyncio
import logging

from engine import coach, speaker, voice
from engine.store import now

log = logging.getLogger("uvicorn.error")


async def run_checkin(app, state, why: str) -> dict:
    store = app.state.store
    entry = {"ts": now().isoformat(), "why": why, "score": state.score,
             "streak_s": state.streak_s, "top": state.top}
    try:
        context = coach.build_context(state)
        text = await asyncio.to_thread(coach.generate, context)
        audio = await asyncio.to_thread(voice.synthesize, text)
        delivered = await asyncio.to_thread(speaker.deliver, text, audio)
        entry |= {"text": text, "delivered": delivered, "has_audio": bool(audio)}
        log.info("check-in (%s) via %s: %s", why, delivered, text)
    except Exception as exc:
        entry |= {"text": None, "error": str(exc), "delivered": "failed"}
        log.exception("check-in failed")
    finally:
        store.append_checkin(entry)
        app.state.speaking = False
    return entry
