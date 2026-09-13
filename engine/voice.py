"""ElevenLabs text-to-speech, and the mailbox the ESP32 collects from.

The laptop hosts; the ESP32 polls it over the LAN. The engine never dials the device:

    mentor.speak()                       ESP32 loop
      ElevenLabs -> PCM bytes              every ~2s: GET /speak/pending
      park in the mailbox        <------   204 No Content   nothing to say
                                 <------   200 + WAV bytes  stream to I2S, play
                                 ------>   POST /speak/{id}/done

Inverting it this way means the engine never has to know the ESP32's address - DHCP can move
the device freely, and only the device holds a hard-coded IP (this laptop's). It also lets the
ESP32 read at its own pace, which matters when it has ~320 KB of RAM shared with the WiFi stack
and a clip is ~32 KB per second of speech.

Audio is raw PCM 16 kHz 16-bit mono, wrapped in a WAV header on the way out. The device has no
MP3 decoder, so samples go straight into the I2S buffer.
"""
from __future__ import annotations

import logging
import re
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response

from engine.config import (AUDIO_DIR, ELEVEN_API_KEY, ELEVEN_FORMAT, ELEVEN_MODEL,
                           ELEVEN_STT_MODEL, ELEVEN_VOICE_ID, SPEAK_SAMPLE_RATE)
from engine.store_helpers import now

try:
    from elevenlabs.client import AsyncElevenLabs
except ImportError:          # the engine still runs; Buddy just has no voice
    AsyncElevenLabs = None

log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/speak", tags=["speak"])
# The watch firmware calls these three by name at the server root. They are the contract with
# the device - renaming one means reflashing, so they live apart from the /speak helpers above.
device = APIRouter(tags=["device"])

_client = None               # built once; a client per nudge is pure overhead
_pending: Clip | None = None
_spoken = 0
_last_poll: datetime | None = None   # when the watch last asked - our only liveness signal


@dataclass
class Clip:
    """One thing waiting to be said, or the last thing that was."""
    text: str
    pcm: bytes
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=now)
    delivered_at: datetime | None = None
    done_at: datetime | None = None

    @property
    def seconds(self) -> float:
        return len(self.pcm) / (SPEAK_SAMPLE_RATE * 2)   # 16-bit mono = 2 bytes per sample


# --- text to speech ------------------------------------------------------------------------

async def synthesize(text: str) -> bytes | None:
    """Render text to raw PCM. Returns None on any failure - never raises.

    This runs on the MATLAB worker behind mentor.speak(), so an exception escaping here could
    stall the queue. A silent nudge is a nuisance; a stalled worker is silent forever.
    """
    if AsyncElevenLabs is None or not ELEVEN_API_KEY:
        log.warning("voice: no ElevenLabs (%s)",
                    "package missing" if AsyncElevenLabs is None else "no API key in .env")
        return None
    try:
        stream = _eleven().text_to_speech.convert(
            voice_id=ELEVEN_VOICE_ID,
            text=text,
            model_id=ELEVEN_MODEL,
            output_format=ELEVEN_FORMAT,
        )
        chunks = [chunk async for chunk in stream]
    except Exception as exc:
        log.warning("voice: tts failed (%s: %s)", type(exc).__name__, exc)
        return None
    return b"".join(chunks)


def _eleven():
    global _client
    if _client is None:
        _client = AsyncElevenLabs(api_key=ELEVEN_API_KEY)
    return _client


async def transcribe(wav_bytes: bytes) -> str | None:
    """Scribe speech-to-text. Returns the text, or None on any failure."""
    if AsyncElevenLabs is None or not ELEVEN_API_KEY:
        return None
    try:
        result = await _eleven().speech_to_text.convert(
            file=("audio.wav", wav_bytes, "audio/wav"),
            model_id=ELEVEN_STT_MODEL,
            # Scribe labels non-speech audio by default - a second of room noise comes back as
            # "[outro jingle]" or "[music]", which then gets asked to Gemini as if it were a
            # question. We only ever want words here.
            tag_audio_events=False,
        )
    except Exception as exc:
        log.warning("voice: stt failed (%s: %s)", type(exc).__name__, exc)
        return None
    return _spoken_words(result.text or "")


# Anything Scribe still wraps in brackets is a sound it recognised, not a word the user said.
_TAG = re.compile(r"\[[^\]]*\]")


def _spoken_words(text: str) -> str | None:
    """Strip audio-event tags and return None when nothing was actually said."""
    words = " ".join(_TAG.sub(" ", text).split())
    # Keep the punctuation - a trailing "?" is the difference between a question and a
    # statement to Gemini. Reject only what has no actual word left in it.
    return words if any(ch.isalnum() for ch in words) else None


def pcm_to_wav(pcm: bytes, sample_rate: int = SPEAK_SAMPLE_RATE,
               channels: int = 1, bit_depth: int = 16) -> bytes:
    """Wrap raw samples in a 44-byte WAV header so the stream describes itself."""
    byte_rate = sample_rate * channels * bit_depth // 8
    block_align = channels * bit_depth // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(pcm), b"WAVE",
        b"fmt ", 16, 1, channels, sample_rate, byte_rate, block_align, bit_depth,
        b"data", len(pcm),
    )
    return header + pcm


# --- the mailbox ---------------------------------------------------------------------------

async def say(text: str) -> Clip | None:
    """Render `text` and leave it for the ESP32. What mentor.speak() calls."""
    global _pending
    pcm = await synthesize(text)
    if not pcm:
        return None
    if _pending and _pending.delivered_at is None:
        # A newer nudge supersedes one the device never collected. Speaking a stale observation
        # minutes late is worse than not speaking it.
        log.info("voice: replacing an uncollected clip (%s)", _pending.id)
    _pending = Clip(text=text, pcm=pcm)
    log.info("voice: queued %s  %.1fs  %d bytes", _pending.id, _pending.seconds, len(pcm))
    return _pending


def state() -> dict:
    """What /health reports."""
    return {
        "configured": bool(AsyncElevenLabs and ELEVEN_API_KEY),
        "voice_id": ELEVEN_VOICE_ID,
        "format": ELEVEN_FORMAT,
        "spoken": _spoken,
        "waiting": bool(_pending and _pending.delivered_at is None),
        "watch_seen": None if _last_poll is None else _last_poll.isoformat(),
        "last": None if _pending is None else {
            "id": _pending.id, "text": _pending.text, "at": _pending.created_at.isoformat(),
            "seconds": round(_pending.seconds, 1),
            "collected": _pending.delivered_at is not None,
            "acked": _pending.done_at is not None,
        },
    }


def seen_recently(within_s: float = 10.0) -> bool:
    """True if the watch polled within the last few seconds - it polls every 2s."""
    return _last_poll is not None and (now() - _last_poll).total_seconds() <= within_s


# --- what the ESP32 calls ------------------------------------------------------------------

@router.get("/pending")
async def pending(format: str = Query("wav", pattern="^(wav|pcm)$")) -> Response:
    """The device's whole job: poll this, play whatever comes back.

    204 No Content means nothing to say - the normal case, and cheap for the device to skip.
    Otherwise the body is the audio and the headers carry the id to acknowledge.

    Serving marks the clip collected, so a device that polls again mid-playback gets 204 rather
    than restarting the same line over itself.
    """
    global _spoken, _last_poll
    # The device polls on a timer whether or not there is anything to say, so the poll itself
    # is the heartbeat - there is no other way to know the watch is alive.
    _last_poll = now()
    if _pending is None or _pending.delivered_at is not None:
        return Response(status_code=204)

    _pending.delivered_at = now()
    _spoken += 1
    body = _pending.pcm if format == "pcm" else pcm_to_wav(_pending.pcm)
    log.info("voice: -> esp32  %s  %d bytes (%s)", _pending.id, len(body), format)
    return Response(
        content=body,
        media_type="audio/wav" if format == "wav" else "application/octet-stream",
        headers={
            "X-Buddy-Id": _pending.id,
            "X-Buddy-Rate": str(SPEAK_SAMPLE_RATE),
            # ASCII only: an ESP32 header parser should not have to handle UTF-8.
            "X-Buddy-Text": _pending.text.encode("ascii", "replace").decode()[:120],
        },
    )


@router.post("/{clip_id}/done")
async def done(clip_id: str) -> dict:
    """Optional acknowledgement, so the logs show what was actually played."""
    if _pending and _pending.id == clip_id:
        _pending.done_at = now()
        log.info("voice: esp32 finished %s", clip_id)
        return {"id": clip_id, "acked": True}
    return {"id": clip_id, "acked": False}


@router.get("")
async def status() -> dict:
    return state()


@router.post("/test")
async def test(text: str = Query("Buddy is connected and ready.")) -> dict:
    """Queue a line by hand - lets you bring up the ESP32 without waiting for a real trigger."""
    clip = await say(text)
    if clip is None:
        return {"queued": False, "reason": "text to speech failed - check the engine log"}
    return {"queued": True, "id": clip.id, "seconds": round(clip.seconds, 1),
            "bytes": len(clip.pcm), "text": text}


# --- the contract with the watch firmware ---------------------------------------------------

@device.get("/pending-speech")
async def pending_speech() -> Response:
    """What the watch polls every 2s. Same mailbox as /speak/pending, the name the device uses.

    The firmware acts only on `200 with a non-empty body`, so anything else is a quiet no-op -
    204 costs the device one header parse and it goes back to sleep.
    """
    return await pending(format="wav")


@device.post("/voice")
async def voice(request: Request) -> Response:
    """Push-to-talk: raw PCM in, spoken answer out.

    The watch POSTs `audio/l16; rate=16000; channels=1` - headerless 16-bit mono samples - and
    plays whatever audio comes back. Anything other than 200 makes it fall back to the canned
    network_issue.wav, so failures here should be status codes, not empty 200s.
    """
    pcm = await request.body()
    if len(pcm) < 3200:                      # under 0.1s - a slip of the button
        raise HTTPException(400, "too short")

    # Scribe wants a real file; the device sends bare samples, so put a header on them.
    heard = await transcribe(pcm_to_wav(pcm))
    if not heard:
        log.info("voice: <- watch  %.1fs, nothing transcribed", len(pcm) / (SPEAK_SAMPLE_RATE * 2))
        raise HTTPException(503, "could not transcribe")
    log.info("voice: <- watch  %.1fs  \"%s\"", len(pcm) / (SPEAK_SAMPLE_RATE * 2), heard)

    from engine import mentor                # imported here: mentor imports voice at module load
    reply = await mentor.answer(heard, request.app.state.pool)
    if not reply:
        raise HTTPException(503, "no answer")
    log.warning("buddy replies: %s", reply)

    audio = await synthesize(reply)
    if not audio:
        raise HTTPException(503, "could not synthesize")
    return Response(content=pcm_to_wav(audio), media_type="audio/wav",
                    headers={"X-Buddy-Heard": heard.encode("ascii", "replace").decode()[:120],
                             "X-Buddy-Text": reply.encode("ascii", "replace").decode()[:120]})


@device.get("/audio/{name}")
async def canned(name: str) -> Response:
    """The offline fallbacks the watch caches into FFat at boot."""
    path = (AUDIO_DIR / name).resolve()
    if path.parent != AUDIO_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "no such clip")
    return Response(content=path.read_bytes(), media_type="audio/wav")


CANNED = {
    "off_task.wav": ("You have senior design until 10. You can play after that. "
                     "You'll regret this block later - go back to the project."),
    "goals_ok.wav": ("Got both. Send the email first, that's the short one. "
                     "Then you have a straight run at senior design until 10."),
    "network_issue.wav": "Sorry, I am facing a network issue right now.",
}


@device.post("/audio/generate")
async def generate_canned(force: bool = Query(False)) -> dict:
    """Render the canned lines to disk. Run once; the watch pulls them on its next boot."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, text in CANNED.items():
        path = AUDIO_DIR / name
        if path.exists() and not force:
            made[name] = f"kept ({path.stat().st_size} bytes)"
            continue
        pcm = await synthesize(text)
        if not pcm:
            made[name] = "failed"
            continue
        path.write_bytes(pcm_to_wav(pcm))
        made[name] = f"wrote {path.stat().st_size} bytes"
    return made
