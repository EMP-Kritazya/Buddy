"""Buddy productivity classifier.
Layer A: rule-based (ships tonight).
Layer B: sklearn on synthetic rows (Saturday only, falls back to rules if confidence < 0.6).
"""
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass
class Classification:
    score: int          # 0-100
    label: str          # productive | unproductive | mixed | idle | break
    category: str       # work | comms | gaming | video | social | idle | other
    confidence: float   # 0.0-1.0


# ---------------------------------------------------------------------------
# Layer A — rules
# ---------------------------------------------------------------------------

_PRODUCTIVE_APPS = {
    "code", "cursor", "matlab", "winword", "word", "overleaf",
    "pycharm", "intellij", "rider", "clion", "webstorm",
    "notepad++", "sublime_text", "vim", "nvim", "emacs",
    "arduino ide", "platformio",
}
_PRODUCTIVE_TITLES = re.compile(
    r"visual studio code|vs code|cursor|matlab|overleaf|"
    r"google docs|google sheets|gmail compose|microsoft word|"
    r"senior design|lab report|homework|assignment",
    re.I,
)

_COMMS_APPS = {"slack", "outlook", "thunderbird", "teams", "discord"}
_COMMS_TITLES = re.compile(r"gmail|inbox|email|outlook|slack|teams", re.I)

_GAMING_APPS = {
    "league of legends", "leagueclient", "leagueclientux", "league of legends.exe",
    "riotclientservices", "riot client",
    "steam", "epicgames", "epicgameslauncher",
    "valorant", "csgo", "cs2", "fortnite", "minecraft",
}
_GAMING_TITLES = re.compile(
    r"league of legends|valorant|counter-strike|fortnite|minecraft|steam",
    re.I,
)
_SOCIAL_TITLES = re.compile(r"instagram|tiktok|twitter|facebook|reddit", re.I)
_VIDEO_APPS = {"netflix", "hulu", "disneyplus", "vlc", "mpc-hc"}
_SHORTS_TITLES = re.compile(r"youtube shorts|shorts", re.I)
_TUTORIAL_TITLES = re.compile(r"tutorial|lecture|course|learn|how to|mit ocw", re.I)


def classify(
    app: str,
    window_title: str,
    idle_s: int = 0,
    open_tasks: list[dict] | None = None,
) -> Classification:
    app_lc = app.lower().strip()
    title_lc = window_title.lower().strip()
    blob = f"{app_lc} {title_lc}"

    # idle overrides everything when a deadline task is open
    has_deadline_task = any(
        t.get("deadline") for t in (open_tasks or []) if t.get("status") == "open"
    )
    if idle_s > 60 and has_deadline_task:
        return Classification(20, "idle", "idle", 0.95)

    if idle_s > 300:
        return Classification(0, "idle", "idle", 0.99)

    # gaming — process name OR window title (venue HTML title trick)
    if any(g in app_lc for g in _GAMING_APPS) or _GAMING_TITLES.search(title_lc):
        return Classification(12, "unproductive", "gaming", 0.97)

    # social / shorts
    if _SOCIAL_TITLES.search(title_lc):
        return Classification(10, "unproductive", "social", 0.92)
    if _SHORTS_TITLES.search(title_lc):
        return Classification(15, "unproductive", "video", 0.90)

    # video streaming
    if any(v in app_lc for v in _VIDEO_APPS):
        return Classification(8, "unproductive", "video", 0.95)

    # YouTube — distinguish tutorial vs casual
    if "youtube" in blob:
        if _TUTORIAL_TITLES.search(title_lc):
            return Classification(70, "mixed", "video", 0.75)
        return Classification(25, "unproductive", "video", 0.82)

    # productive apps / titles
    if any(p in app_lc for p in _PRODUCTIVE_APPS) or _PRODUCTIVE_TITLES.search(title_lc):
        return Classification(85, "productive", "work", 0.92)

    # Discord is unproductive for demo (chat drift), unless title looks like work
    if "discord" in app_lc:
        return Classification(25, "unproductive", "comms", 0.85)

    # comms — mixed productivity
    if any(c in app_lc for c in _COMMS_APPS) or _COMMS_TITLES.search(title_lc):
        return Classification(55, "mixed", "comms", 0.78)

    # generic browser
    if "chrome" in app_lc or "firefox" in app_lc or "msedge" in app_lc or "edge" in app_lc:
        return Classification(50, "mixed", "other", 0.60)

    return Classification(50, "mixed", "other", 0.50)


# ---------------------------------------------------------------------------
# Layer B — sklearn (Saturday, optional)
# ---------------------------------------------------------------------------

def load_model(model_path: str = "ml/buddy_model.pkl"):
    """Load a pre-trained sklearn pipeline if it exists."""
    import pickle
    import pathlib
    p = pathlib.Path(model_path)
    if p.exists():
        with open(p, "rb") as f:
            return pickle.load(f)
    return None


def classify_ml(
    app: str,
    window_title: str,
    idle_s: int = 0,
    open_tasks: list[dict] | None = None,
    model=None,
) -> Classification:
    """Try ML model, fall back to rules if confidence < 0.6."""
    if model is None:
        return classify(app, window_title, idle_s, open_tasks)

    features = [app.lower(), window_title.lower(), idle_s]
    try:
        proba = model.predict_proba([features])[0]
        confidence = float(max(proba))
        if confidence < 0.6:
            return classify(app, window_title, idle_s, open_tasks)
        label_idx = int(proba.argmax())
        label = model.classes_[label_idx]
        score = {"productive": 85, "mixed": 50, "unproductive": 15, "idle": 10, "break": 40}.get(label, 50)
        return Classification(score, label, "other", confidence)
    except Exception:
        return classify(app, window_title, idle_s, open_tasks)


if __name__ == "__main__":
    tests = [
        ("League of Legends", "League of Legends", 0),
        ("chrome", "League of Legends", 0),  # HTML title trick
        ("Code", "buddy - Visual Studio Code", 0),
        ("chrome", "YouTube - tutorial how to use timescaledb", 0),
        ("chrome", "YouTube Shorts", 0),
        ("Code", "VS Code", 65),  # idle during deadline
    ]
    for app, title, idle in tests:
        c = classify(app, title, idle, [{"deadline": "2099-09-12T22:00:00", "status": "open"}])
        print(f"{app:30s} | {title:45s} | idle={idle:3d}s -> {c.score:3d} {c.label:15s} ({c.confidence:.2f})")
