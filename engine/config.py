"""Every knob in one place. Thresholds are read from the environment so the demo can be
retuned without editing code."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Overridable so tests (and a second profile) never touch the real log.
DATA_DIR = Path(os.environ.get("BUDDY_DATA_DIR", ROOT / "data"))
SESSIONS_FILE = DATA_DIR / "sessions.jsonl"
SCORES_FILE = DATA_DIR / "scores.jsonl"
CHECKINS_FILE = DATA_DIR / "checkins.jsonl"
MODEL_FILE = ROOT / "ml" / "model.joblib"


def _num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# --- the loop ---
TICK_SECONDS = _num("BUDDY_TICK_SECONDS", 15)
WINDOW_MINUTES = _num("BUDDY_WINDOW_MINUTES", 10)

# --- when Buddy is allowed to speak ---
SCORE_THRESHOLD = _num("BUDDY_SCORE_THRESHOLD", 0.35)   # 0-1, time-weighted
STREAK_SECONDS = _num("BUDDY_STREAK_SECONDS", 45)       # sustained off-task time
COOLDOWN_SECONDS = _num("BUDDY_COOLDOWN_SECONDS", 180)  # silence after a check-in
MIN_TRACKED_SECONDS = _num("BUDDY_MIN_TRACKED_SECONDS", 60)  # too little data to judge
PRESENCE_TIMEOUT_S = _num("BUDDY_PRESENCE_TIMEOUT_S", 120)   # browser quiet = user elsewhere

PRODUCTIVE_AT = 0.5  # p above this counts as productive time

DATA_DIR.mkdir(exist_ok=True)
