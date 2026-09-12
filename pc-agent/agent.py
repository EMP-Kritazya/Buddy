"""Buddy PC agent — Windows foreground window logger + coaching trigger.
Polls every 1 s, POSTs to /events, writes buddy_score.csv, fires /coach on slumps.
"""
from __future__ import annotations
import csv
import ctypes
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BUDDY_API", "http://127.0.0.1:8000")
CSV_PATH = pathlib.Path(__file__).parent.parent / "buddy_score.csv"
TRIGGERS_PATH = pathlib.Path(__file__).parent / "triggers.json"

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from ml.classify import classify

# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

user32 = ctypes.windll.user32
psapi = ctypes.windll.psapi

def _foreground_app_title() -> tuple[str, str]:
    """Return (exe_name, window_title) of the foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("", "")

    # window title
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value

    # exe name
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h_proc = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
    if h_proc:
        exe_buf = ctypes.create_unicode_buffer(260)
        psapi.GetModuleFileNameExW(h_proc, None, exe_buf, 260)
        ctypes.windll.kernel32.CloseHandle(h_proc)
        exe = pathlib.Path(exe_buf.value).stem.lower()
    else:
        exe = ""

    return (exe, title)


def _idle_seconds() -> int:
    """Seconds since last user input (keyboard or mouse)."""
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    elapsed_ms = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return max(0, elapsed_ms // 1000)


# ---------------------------------------------------------------------------
# Trigger logic
# ---------------------------------------------------------------------------

def _load_triggers() -> dict:
    if TRIGGERS_PATH.exists():
        return json.loads(TRIGGERS_PATH.read_text())
    return {
        "score_threshold": 35,
        "streak_seconds": 45,
        "cooldown_seconds": 180,
        "require_open_deadline_task": True,
    }


def _open_tasks() -> list[dict]:
    try:
        r = requests.get(f"{BASE_URL}/tasks", timeout=2)
        return r.json() if r.ok else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def _write_csv(ts: str, score: int, app: str):
    exists = CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "score", "app"])
        w.writerow([ts, score, app])


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    print(f"[Buddy PC agent] → {BASE_URL}")
    print(f"[Buddy PC agent] CSV → {CSV_PATH}")

    triggers = _load_triggers()
    score_history: list[tuple[float, int]] = []  # (time, score)
    last_coach_time = 0.0
    last_app = ""
    last_log_time = 0.0

    while True:
        now_mono = time.monotonic()
        app, title = _foreground_app_title()
        idle_s = _idle_seconds()
        changed = app != last_app
        elapsed = now_mono - last_log_time

        if changed or elapsed >= 5:
            tasks = _open_tasks()
            c = classify(app, title, idle_s, tasks)
            ts_iso = datetime.now(timezone.utc).isoformat()

            print(f"[{ts_iso[:19]}] {app:30s} | score={c.score:3d} {c.label}")

            # POST /events
            try:
                requests.post(
                    f"{BASE_URL}/events",
                    json={
                        "ts": ts_iso,
                        "source": "pc",
                        "app": app,
                        "window_title": title,
                        "category": c.category,
                        "label": c.label,
                        "score": c.score,
                        "confidence": c.confidence,
                        "duration_s": int(elapsed) if not changed else 0,
                        "idle_s": idle_s,
                        "active_task_id": _active_task_id(tasks, ts_iso),
                    },
                    timeout=2,
                )
            except Exception as e:
                print(f"  [warn] /events: {e}")

            # CSV
            _write_csv(ts_iso, c.score, app)

            # Slump detection
            score_history.append((now_mono, c.score))
            # prune older than streak_seconds
            cutoff = now_mono - triggers["streak_seconds"]
            score_history = [(t, s) for t, s in score_history if t >= cutoff]

            if len(score_history) >= 3:
                avg = sum(s for _, s in score_history) / len(score_history)
                cooldown_ok = (now_mono - last_coach_time) > triggers["cooldown_seconds"]
                threshold_ok = avg < triggers["score_threshold"]
                deadline_ok = (
                    not triggers["require_open_deadline_task"]
                    or any(t.get("deadline") for t in tasks if t.get("status") == "open")
                )

                if threshold_ok and cooldown_ok and deadline_ok:
                    last_coach = _last_productive_app(score_history, app)
                    _fire_coach(tasks, app, int(avg), int(now_mono - last_coach_time), last_coach)
                    last_coach_time = now_mono
                    score_history.clear()

            last_app = app
            last_log_time = now_mono

        time.sleep(1)


def _active_task_id(tasks: list[dict], ts_iso: str) -> str | None:
    """Return the id of the first open task whose deadline hasn't passed, if any."""
    for t in tasks:
        if t.get("status") == "open":
            if t.get("deadline"):
                try:
                    dl = datetime.fromisoformat(t["deadline"].replace("Z", "+00:00"))
                    if dl > datetime.fromisoformat(ts_iso):
                        return t.get("id")
                except Exception:
                    pass
            else:
                return t.get("id")
    return None


def _last_productive_app(history: list[tuple[float, int]], current: str) -> str:
    for _, s in reversed(history):
        if s >= 60:
            return current
    return "VS Code"


def _fire_coach(tasks, current_app, avg_score, streak_s, last_productive):
    now_str = datetime.now().strftime("%H:%M")
    task_titles = [t["title"] for t in tasks if t.get("status") == "open"]
    payload = {
        "tasks": task_titles,
        "now": now_str,
        "current_app": current_app,
        "score": avg_score,
        "unproductive_streak_s": streak_s,
        "last_productive_app": last_productive,
    }
    try:
        r = requests.post(f"{BASE_URL}/coach", json=payload, timeout=10)
        if r.ok:
            print(f"  [coach] fired → {r.json().get('spoken','')}")
    except Exception as e:
        print(f"  [warn] /coach: {e}")


if __name__ == "__main__":
    main()
