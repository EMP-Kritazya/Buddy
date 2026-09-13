"""Every knob in one place. Values are read from the environment so they can be changed
without editing code."""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.environ.get("BUDDY_DATA_DIR", ROOT / "data"))

SESSIONS_FILE = DATA_DIR / "sessions.jsonl"   # raw sensor log, append-only, replayable
MODEL_FILE = ROOT / "ml" / "model.joblib"


def _num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# the running productivity score, 0-1
SCORE_START = _num("BUDDY_SCORE_START", 0.5)              # neutral on a fresh database
SCORE_TAU_SECONDS = _num("BUDDY_SCORE_TAU_SECONDS", 300)  # 5 min of memory

def _local_tz() -> str:
    """The user's IANA zone, e.g. 'America/Chicago'.

    Goals are a human, local-day idea: "today" ends when you go to bed, not at 7pm because the
    database happens to run in UTC. Every day-bounded query converts to this zone first.
    """
    tz = os.environ.get("BUDDY_TZ") or os.environ.get("TZ")
    if tz:
        return tz
    with contextlib.suppress(Exception):
        parts = Path("/etc/localtime").resolve().parts
        if "zoneinfo" in parts:
            return "/".join(parts[parts.index("zoneinfo") + 1:])
    return "UTC"


LOCAL_TZ = _local_tz()

# Read here rather than in db.py so it goes through the same .env load as everything else.
# db.py reading os.environ on its own worked only because app.py happened to import config
# first; importing db by itself - a script, a test - found nothing.
DATABASE_URL = os.environ.get("TIMESCALE_SERVICE_URL") or os.environ.get("DATABASE_URL", "")

# ElevenLabs turns the nudge into sound. Accepts either key name - the .env here uses
# ELEVEN_API, the standalone helper script used ELEVENLABS_API_KEY.
ELEVEN_API_KEY = (os.environ.get("ELEVENLABS_API_KEY")
                  or os.environ.get("ELEVEN_API", ""))
ELEVEN_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVEN_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
# Raw PCM, 16 kHz, 16-bit mono: straight into the ESP32's I2S buffer with no decoding. The
# device has no MP3 decoder, so this is not a preference - it is the only thing it can play.
SPEAK_SAMPLE_RATE = int(_num("BUDDY_SPEAK_RATE", 16000))
# Canned lines the watch caches in FFat at boot, so it still speaks with no network.
AUDIO_DIR = ROOT / "audio"
# Speech-to-text for the push-to-talk button.
ELEVEN_STT_MODEL = os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v2")
ELEVEN_FORMAT = f"pcm_{SPEAK_SAMPLE_RATE}"

# Google Maps. Only the Routes API is needed: it accepts a plain address string as the
# destination, so there is no separate geocoding step.
MAPS_API_KEY = os.environ.get("MAPS_API", "")
# How stale a location fix can be before Buddy stops trusting it. The laptop reports where it
# is only while the dashboard is open, so this is generous.
LOCATION_MAX_AGE_S = _num("BUDDY_LOCATION_MAX_AGE_S", 6 * 3600)

# Gemini writes the nudge. The key name matches what is already in .env.
GEMINI_API_KEY = os.environ.get("GEMINI_API", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# Gemini 3 is a thinking model and its reasoning tokens come out of this same budget, so a tight
# cap truncates the answer mid-sentence rather than producing a short one - 400 was still cutting
# replies off at "...your productivity score is at". This is a safety valve, not the length
# control: PERSONA asks for two sentences and _for_speech() enforces it, so a generous ceiling
# costs nothing except the tokens actually used.
GEMINI_MAX_TOKENS = int(_num("GEMINI_MAX_TOKENS", 1000))
GEMINI_TEMPERATURE = _num("GEMINI_TEMPERATURE", 0.9)
# Gemini 3 models reason before answering, which costs latency and output budget that a one-line
# nudge does not need. Not every model accepts every level (MINIMAL is rejected by some), so
# this is a setting: LOW is broadly supported, and "" omits the option entirely.
GEMINI_THINKING = os.environ.get("GEMINI_THINKING", "LOW").upper()

MATLAB_URL = os.environ.get("MATLAB_URL", "")
MATLAB_TOKEN = os.environ.get("MATLAB_TOKEN", "")
MATLAB_FUNCTION = os.environ.get("MATLAB_FUNCTION", "analyze_scores")
MATLAB_ENABLED = os.environ.get("BUDDY_MATLAB_ENABLED", "1") not in ("0", "false", "False")
# How much history rides along with each call. Every processed log is still sent either way -
# this only sets how many trailing points come with it.
#
# It cannot be 1. MATLAB Production Server is stateless: each feval sees only what we send, so
# the soft trigger ("above 0.5 but dropping 3 consecutive readings") is invisible unless at
# least 3 readings are in the payload. 3 is the floor; 20 is what the algorithm was written
# against and leaves room for the trend logic to grow.
MATLAB_WINDOW = max(3, int(_num("MATLAB_WINDOW", 5)))
MATLAB_TIMEOUT_S = _num("MATLAB_TIMEOUT_S", 10)
# Points waiting to be sent. Only a backstop: if MATLAB hangs, this bounds memory instead of
# growing without limit. The scores themselves are already safe in the activity table.
MATLAB_QUEUE_MAX = int(_num("MATLAB_QUEUE_MAX", 500))
# How long Buddy stays quiet after speaking. MATLAB keeps returning a trigger for as long as the
# slump lasts - that is correct of it - so the "don't nag" rule has to live on this side.
MATLAB_COOLDOWN_S = _num("MATLAB_COOLDOWN_S", 30)
# A hard trigger means the score is already below 0.5 - it should not have to wait out a quiet
# period earned by a gentler nudge. It gets its own, shorter one. Set it to 0 to let every
# single hard trigger speak, at the cost of Buddy talking on every log during a long slump.
MATLAB_HARD_COOLDOWN_S = _num("MATLAB_HARD_COOLDOWN_S", 10)
# The ngrok tunnel in front of MATLAB serves a self-signed certificate.
MATLAB_VERIFY_TLS = os.environ.get("MATLAB_VERIFY_TLS", "0") not in ("0", "false", "False")

DATA_DIR.mkdir(exist_ok=True)
