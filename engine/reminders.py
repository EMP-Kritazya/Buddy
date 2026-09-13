"""Reminders: things the user asked to hear about later.

A reminder is not a nudge. MATLAB did not ask for it, the cooldown does not apply to it, and it
is not suppressed for being inconvenient - the user asked for it, so it gets said.

The due time lives in the database, not in a timer, so a reminder set before a restart still
fires after one. This worker does nothing but watch the clock:

    every CHECK_SECONDS: claim anything overdue -> render it -> leave it for the watch
"""
from __future__ import annotations

import asyncio
import logging

from engine import db, voice
from engine.store_helpers import now

log = logging.getLogger("uvicorn.error")

# Ten seconds is close enough for "remind me in twenty minutes" and costs one small indexed
# query per tick.
CHECK_SECONDS = 10.0

_worker: asyncio.Task | None = None
_spoken = 0


def start(pool) -> None:
    global _worker
    if _worker is None or _worker.done():
        _worker = asyncio.create_task(_run(pool), name="reminders")
        log.info("reminders: worker started, checking every %.0fs", CHECK_SECONDS)


async def stop() -> None:
    if _worker is None:
        return
    _worker.cancel()
    try:
        await _worker
    except asyncio.CancelledError:
        pass


async def _run(pool) -> None:
    while True:
        try:
            await _tick(pool)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # One bad tick must not end the loop and leave every future reminder unspoken.
            log.warning("reminders: tick failed (%s: %s)", type(exc).__name__, exc)
        await asyncio.sleep(CHECK_SECONDS)


async def _tick(pool) -> None:
    global _spoken
    due = await db.due_reminders(pool, now())
    if not due:
        return

    # The watch has one mailbox slot, so two reminders arriving together would mean the second
    # silently replacing the first. Say them in one breath instead.
    text = " ".join(r["text"].strip().rstrip(".") + "." for r in due)
    log.warning("reminder: %s", text)

    if await voice.say(text) is None:
        # Text-to-speech is down. The pre-rendered clips cannot carry a custom sentence, so
        # the reminder is already marked fired and the user will not hear it - say so loudly
        # rather than letting it disappear quietly.
        log.error("reminders: could not render %d reminder(s), they were NOT heard", len(due))
        return
    _spoken += len(due)


def state() -> dict:
    return {"running": bool(_worker and not _worker.done()), "spoken": _spoken,
            "check_seconds": CHECK_SECONDS}
