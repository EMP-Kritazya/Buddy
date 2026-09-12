"""ElevenLabs text-to-speech. Returns None when unavailable - a check-in without audio is still
a check-in, and the caller falls back to the laptop speaker."""
from __future__ import annotations

import logging
import os

log = logging.getLogger("uvicorn.error")

VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")


def synthesize(text: str) -> bytes | None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return None
    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=key)
        # PCM so the ESP32 does not have to decode MP3.
        audio = client.text_to_speech.convert(
            voice_id=VOICE_ID, text=text,
            model_id="eleven_turbo_v2_5", output_format="pcm_16000",
        )
        return b"".join(audio)
    except Exception as exc:
        log.warning("voice: tts failed (%s)", exc)
        return None
