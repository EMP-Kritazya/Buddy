"""Buddy PC agent — scrape foreground activity, label, score via local model, feed MATLAB.

Pipeline (Suyog):
  scrape app/title/idle → label → ml.classify (Kritazya) → buddy_score.csv (+ optional POST /events)

Coaching / Gemini triggers are NOT owned here — MATLAB + Tiger Data → Gemini (Sandesh / P2).
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import pathlib
import sys
import time
from datetime import datetime

import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BUDDY_API", "http://127.0.0.1:8000")
CSV_PATH = pathlib.Path(__file__).parent.parent / "buddy_score.csv"
# Optional raw scrape log (app changes) for debugging / Kritazya
SCRAPE_LOG_PATH = pathlib.Path(__file__).parent / "scrape_log.csv"

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from ml.classify import classify  # noqa: E402  — Kritazya's local model / Layer A

# ---------------------------------------------------------------------------
# Windows scrape
# ---------------------------------------------------------------------------

user32 = ctypes.windll.user32
psapi = ctypes.windll.psapi
kernel32 = ctypes.windll.kernel32


def scrape_foreground() -> tuple[str, str]:
    """Return (exe_stem_lower, window_title) of the foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("", "")

    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value

    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h_proc = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
    if h_proc:
        exe_buf = ctypes.create_unicode_buffer(260)
        psapi.GetModuleFileNameExW(h_proc, None, exe_buf, 260)
        kernel32.CloseHandle(h_proc)
        exe = pathlib.Path(exe_buf.value).stem.lower()
    else:
        exe = ""

    return (exe, title)


def scrape_idle_seconds() -> int:
    """Seconds since last keyboard/mouse input."""

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    elapsed_ms = kernel32.GetTickCount() - lii.dwTime
    return max(0, int(elapsed_ms // 1000))


# ---------------------------------------------------------------------------
# Light label (before / alongside the model)
# ---------------------------------------------------------------------------


def label_activity(app: str, title: str, idle_s: int) -> dict:
    """Cheap structural label on the scrape — model still owns the 0–100 score."""
    app_lc = (app or "").lower()
    title_lc = (title or "").lower()
    blob = f"{app_lc} {title_lc}"

    if idle_s > 60:
        kind = "idle"
    elif any(k in blob for k in ("league of legends", "steam", "riot", "valorant")):
        kind = "gaming"
    elif any(k in blob for k in ("youtube shorts", "instagram", "tiktok", "netflix")):
        kind = "distraction"
    elif any(k in app_lc for k in ("code", "cursor", "matlab", "winword")):
        kind = "work"
    elif any(k in app_lc for k in ("chrome", "msedge", "firefox", "edge")):
        kind = "browser"
    elif "discord" in app_lc or "slack" in app_lc:
        kind = "comms"
    else:
        kind = "other"

    return {
        "app": app,
        "window_title": title,
        "idle_s": idle_s,
        "kind": kind,
    }


# ---------------------------------------------------------------------------
# Outputs: scrape log, score CSV, optional Tiger /events
# ---------------------------------------------------------------------------


def append_csv(path: pathlib.Path, header: list[str], row: list) -> None:
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(header)
        w.writerow(row)


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float = 5.0) -> tuple[int, object]:
    """Tiny JSON HTTP helper (stdlib only — no requests)."""
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
            return resp.status, None
        return resp.status, json.loads(raw)


def post_event(api_base: str, payload: dict, dry_run: bool) -> None:
    """Store scored event in Tiger via backend — not a Gemini coach call."""
    url = f"{api_base.rstrip('/')}/events"
    if dry_run:
        print(f"  [dry-run] POST {url} score={payload.get('score')} app={payload.get('app')}")
        return
    try:
        status, _ = _http_json("POST", url, payload, timeout=5.0)
        if status >= 400:
            print(f"  [warn] /events HTTP {status}")
    except Exception as exc:
        print(f"  [warn] /events: {exc}")


def fetch_tasks(api_base: str, dry_run: bool) -> list[dict]:
    """Optional context for the model (open deadlines). Empty if API down."""
    if dry_run:
        return []
    try:
        status, data = _http_json("GET", f"{api_base.rstrip('/')}/tasks", timeout=2.0)
        if status < 400:
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "tasks" in data:
                return list(data["tasks"])
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run(api_base: str, dry_run: bool, no_events: bool) -> None:
    api_base = api_base.rstrip("/")
    print(f"[Buddy PC] scrape → label → ml.classify → CSV")
    print(f"[Buddy PC] api={api_base} dry_run={dry_run} post_events={not no_events}")
    print(f"[Buddy PC] score CSV → {CSV_PATH}")
    print(f"[Buddy PC] scrape log → {SCRAPE_LOG_PATH}")
    print("[Buddy PC] Gemini /coach is owned by MATLAB + Tiger (not this agent)")

    last_app, last_title = "", ""
    last_emit = 0.0
    context_started = time.monotonic()

    while True:
        now_mono = time.monotonic()
        app, title = scrape_foreground()
        idle_s = scrape_idle_seconds()
        changed = (app != last_app) or (title != last_title)

        if changed:
            context_started = now_mono
            print(f"Foreground: {app or '(unknown)'} | {title[:100]}")
            last_app, last_title = app, title

        # Emit on change or every 5s
        if changed or (now_mono - last_emit >= 5.0):
            when = datetime.now().astimezone()
            ts_iso = when.isoformat(timespec="seconds")
            duration_s = int(now_mono - context_started)

            labeled = label_activity(app, title, idle_s)
            tasks = fetch_tasks(api_base, dry_run=dry_run)

            # Kritazya local model (Layer A rules tonight; sklearn later)
            scored = classify(app, title, idle_s, tasks)

            append_csv(
                SCRAPE_LOG_PATH,
                ["timestamp", "app", "window_title", "idle_s", "kind", "duration_s"],
                [ts_iso, app, title, idle_s, labeled["kind"], duration_s],
            )
            append_csv(
                CSV_PATH,
                ["timestamp", "score", "app"],
                [ts_iso, int(scored.score), app],
            )

            event = {
                "ts": ts_iso,
                "source": "pc",
                "app": app,
                "window_title": title,
                "category": scored.category,
                "label": scored.label,
                "score": int(scored.score),
                "confidence": float(scored.confidence),
                "duration_s": duration_s,
                "idle_s": idle_s,
                "active_task_id": None,
                "kind": labeled["kind"],
            }

            print(
                f"[{ts_iso[11:19]}] {app:28s} kind={labeled['kind']:12s} "
                f"score={scored.score:3d} {scored.label}"
            )

            if not no_events:
                post_event(api_base, event, dry_run=dry_run)

            last_emit = now_mono

        time.sleep(1)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Buddy PC scraper: log + label + local model score → CSV for MATLAB"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip HTTP; still scrape, label, score, write CSVs",
    )
    p.add_argument(
        "--no-events",
        action="store_true",
        help="Do not POST /events (CSV only — useful if backend is down)",
    )
    p.add_argument(
        "--api-base",
        default=os.environ.get("BUDDY_API", "http://127.0.0.1:8000"),
        help="Backend base URL for optional POST /events and GET /tasks",
    )
    args = p.parse_args()
    try:
        run(api_base=args.api_base, dry_run=args.dry_run, no_events=args.no_events)
    except KeyboardInterrupt:
        print("[Buddy PC] stopped.")


if __name__ == "__main__":
    main()
