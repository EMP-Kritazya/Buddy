"""ElevenLabs Scribe STT + TTS helper.
Keys in .env / NordPass. Call from backend — never from the watch.
"""
from __future__ import annotations

import os
import pathlib
import struct

# Load D:\Buddy\.env if present (does not override existing env vars)
_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = _REPO / ".env"


def _load_dotenv(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv(_ENV)

from elevenlabs import ElevenLabs  # noqa: E402

ELEVEN_API_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")

_client = ElevenLabs(api_key=ELEVEN_API_KEY)


def transcribe(wav_bytes: bytes, language: str = "eng") -> str:
    """Scribe v2 STT. Returns plain text."""
    result = _client.speech_to_text.convert(
        file=("audio.wav", wav_bytes, "audio/wav"),
        model_id="scribe_v2",
        language_code=language,
    )
    return result.text.strip()


def speak(text: str) -> bytes:
    """TTS -> raw PCM 16 kHz 16-bit mono (no MP3 decode on ESP32)."""
    audio = _client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="pcm_16000",
    )
    return b"".join(audio)


def speak_wav(text: str) -> bytes:
    """TTS -> WAV file bytes (PCM wrapped in a WAV header)."""
    pcm = speak(text)
    return _pcm_to_wav(pcm, sample_rate=16000, channels=1, bit_depth=16)


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000, channels: int = 1, bit_depth: int = 16) -> bytes:
    byte_rate = sample_rate * channels * bit_depth // 8
    block_align = channels * bit_depth // 8
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
        b"data",
        data_size,
    )
    return header + pcm


def generate_canned() -> None:
    audio_dir = _REPO / "audio"
    watch_data = _REPO / "watch" / "data"
    audio_dir.mkdir(parents=True, exist_ok=True)
    watch_data.mkdir(parents=True, exist_ok=True)

    off_task = (
        "You have senior design until 10. You can play after that. "
        "You'll regret this block later — go back to the project."
    )
    goals_ok = (
        "Got both. Send the email first — that's the short one. "
        "Then you have a straight run at senior design until 10."
    )

    for name, text in (("off_task.wav", off_task), ("goals_ok.wav", goals_ok)):
        wav = speak_wav(text)
        for dest in (audio_dir / name, watch_data / name):
            dest.write_bytes(wav)
            print(f"Wrote {dest} ({len(wav)} bytes)")


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        wav = pathlib.Path(sys.argv[1]).read_bytes()
        print("Transcription:", transcribe(wav))
    else:
        generate_canned()
