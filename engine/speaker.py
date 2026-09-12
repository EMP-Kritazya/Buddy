"""Delivery. The ESP32 POLLS for pending audio, so the engine never needs to know the device's
IP - which matters on hackathon wifi where addresses move. If no device has checked in
recently, Buddy speaks through the laptop instead so the loop is always demonstrable."""
from __future__ import annotations

import logging
import os
import platform
import subprocess
from datetime import datetime, timedelta, timezone

log = logging.getLogger("uvicorn.error")

DEVICE_TIMEOUT = timedelta(seconds=30)

_pending: list[dict] = []
_last_poll: datetime | None = None


def device_polled() -> None:
    global _last_poll
    _last_poll = datetime.now(timezone.utc)


def device_online() -> bool:
    return bool(_last_poll and datetime.now(timezone.utc) - _last_poll < DEVICE_TIMEOUT)


def take_pending() -> dict | None:
    device_polled()
    return _pending.pop(0) if _pending else None


def deliver(text: str, audio: bytes | None) -> str:
    if device_online():
        _pending.append({"text": text, "audio_len": len(audio or b"")})
        return "esp32"
    return _speak_locally(text)


def _speak_locally(text: str) -> str:
    if os.environ.get("BUDDY_MUTE"):  # tests and quiet demos
        log.info("BUDDY (muted): %s", text)
        return "muted"
    if platform.system() == "Darwin":
        try:
            subprocess.Popen(["say", text])
            return "laptop"
        except Exception as exc:
            log.warning("speaker: local playback failed (%s)", exc)
    log.info("BUDDY SAYS: %s", text)
    return "log"
