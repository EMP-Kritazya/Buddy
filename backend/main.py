"""Buddy backend — FastAPI.
Owns: Tiger Data, Gemini task memory, /voice brain, /coach brain, /pending-speech queue.
"""
from __future__ import annotations
import asyncio
import json
import os
import pathlib
import queue
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from ml.classify import classify
from voice.eleven import transcribe, speak_wav

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.0-flash"

TIGER_DSN = os.environ.get("TIGER_DSN", "")  # set from NordPass
SQLITE_PATH = pathlib.Path(__file__).parent / "fallback.db"

# In-memory audio queue for proactive coaching (GET /pending-speech)
_speech_queue: queue.Queue[bytes] = queue.Queue()

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_conn():
    if TIGER_DSN:
        return psycopg2.connect(TIGER_DSN, cursor_factory=psycopg2.extras.RealDictCursor)
    return None


def _sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_sqlite():
    conn = _sqlite()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            deadline TEXT,
            priority INTEGER,
            status TEXT DEFAULT 'open',
            estimate_min INTEGER,
            created_ts TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS events (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            source TEXT,
            app TEXT,
            window_title TEXT,
            category TEXT,
            label TEXT,
            score INTEGER,
            confidence REAL,
            duration_s INTEGER,
            idle_s INTEGER,
            active_task_id TEXT
        );
        CREATE TABLE IF NOT EXISTS incidents (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            kind TEXT,
            summary TEXT,
            spoken_text TEXT,
            app TEXT,
            score INTEGER
        );
    """)
    conn.commit()
    conn.close()


_init_sqlite()

# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Buddy, a focused productivity coach on the user's wrist.
You remember the user's goals for today.
When the user speaks goals, return JSON exactly:
{
  "reply": "spoken sentences under 20 seconds",
  "tasks_add": [{"title": "...", "deadline": "ISO or null", "priority": 1, "estimate_min": null}],
  "tasks_update": [{"id": "task_id", "status": "done"}]
}
Suggest the shortest task first. No medical advice. Be direct and warm, one sentence each."""

COACH_PROMPT_TEMPLATE = """Tasks today:
{task_list}

Now: {now}. App open: {current_app}. Productivity score: {score}/100 for {streak}s.
Last productive app: {last_productive_app}.

Write ONE spoken coaching sentence. Name the deadline. Do not shame. Under 15 words."""


def _get_tasks_for_gemini(conn=None) -> list[dict]:
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE status='open' ORDER BY priority")
        return [dict(r) for r in cur.fetchall()]
    db = _sqlite()
    rows = db.execute("SELECT * FROM tasks WHERE status='open' ORDER BY priority").fetchall()
    db.close()
    return [dict(r) for r in rows]


def _gemini_voice(text: str, tasks: list[dict]) -> dict:
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json"},
    )
    task_ctx = json.dumps(tasks, default=str)
    response = model.generate_content(
        f"Current tasks: {task_ctx}\n\nUser said: {text}"
    )
    return json.loads(response.text)


def _gemini_coach(payload: dict, tasks: list[dict]) -> str:
    task_list = "\n".join(
        f"{i+1}) {t['title']}" + (f" until {t['deadline']}" if t.get("deadline") else "")
        for i, t in enumerate(tasks)
    )
    prompt = COACH_PROMPT_TEMPLATE.format(
        task_list=task_list or "No tasks set",
        now=payload.get("now", "unknown"),
        current_app=payload.get("current_app", "unknown"),
        score=payload.get("score", 0),
        streak=payload.get("unproductive_streak_s", 0),
        last_productive_app=payload.get("last_productive_app", "unknown"),
    )
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text.strip()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Buddy API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# POST /voice
# ---------------------------------------------------------------------------

@app.post("/voice")
async def voice(audio: UploadFile = File(...)):
    """Receive WAV from watch → STT → Gemini → TTS → return WAV."""
    wav_bytes = await audio.read()

    # STT
    try:
        text = transcribe(wav_bytes)
    except Exception as e:
        raise HTTPException(500, f"STT failed: {e}")

    # Gemini
    tasks = _get_tasks_for_gemini()
    try:
        result = _gemini_voice(text, tasks)
    except Exception as e:
        raise HTTPException(500, f"Gemini failed: {e}")

    reply_text = result.get("reply", "Got it.")

    # Persist tasks
    db = _sqlite()
    now_iso = datetime.now(timezone.utc).isoformat()
    for t in result.get("tasks_add", []):
        t_id = "task_" + uuid.uuid4().hex[:8]
        db.execute(
            "INSERT OR REPLACE INTO tasks(id,title,deadline,priority,status,estimate_min,created_ts) "
            "VALUES(?,?,?,?,?,?,?)",
            (t_id, t["title"], t.get("deadline"), t.get("priority", 1),
             "open", t.get("estimate_min"), now_iso),
        )
    for u in result.get("tasks_update", []):
        db.execute("UPDATE tasks SET status=? WHERE id=?", (u["status"], u["id"]))
    db.commit()
    db.close()

    # TTS
    try:
        wav_out = speak_wav(reply_text)
    except Exception:
        wav_out = _load_canned("goals_ok.wav")

    return Response(content=wav_out, media_type="audio/wav")


# ---------------------------------------------------------------------------
# POST /events
# ---------------------------------------------------------------------------

class EventRow(BaseModel):
    ts: str | None = None
    source: str = "pc"
    app: str
    window_title: str
    category: str | None = None
    label: str | None = None
    score: int | None = None
    confidence: float | None = None
    duration_s: int = 0
    idle_s: int = 0
    active_task_id: str | None = None


@app.post("/events", status_code=201)
def post_event(ev: EventRow):
    if ev.ts is None:
        ev.ts = datetime.now(timezone.utc).isoformat()
    if ev.score is None:
        tasks = _get_tasks_for_gemini()
        c = classify(ev.app, ev.window_title, ev.idle_s, tasks)
        ev.score = c.score
        ev.label = c.label
        ev.category = c.category
        ev.confidence = c.confidence

    # Tiger Data (TimescaleDB)
    tiger = _get_conn()
    if tiger:
        try:
            cur = tiger.cursor()
            cur.execute(
                "INSERT INTO events(ts,source,app,window_title,category,label,score,"
                "confidence,duration_s,idle_s,active_task_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (ev.ts, ev.source, ev.app, ev.window_title, ev.category, ev.label,
                 ev.score, ev.confidence, ev.duration_s, ev.idle_s, ev.active_task_id),
            )
            tiger.commit()
        finally:
            tiger.close()
    else:
        db = _sqlite()
        db.execute(
            "INSERT INTO events(ts,source,app,window_title,category,label,score,"
            "confidence,duration_s,idle_s,active_task_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ev.ts, ev.source, ev.app, ev.window_title, ev.category, ev.label,
             ev.score, ev.confidence, ev.duration_s, ev.idle_s, ev.active_task_id),
        )
        db.commit()
        db.close()

    return {"ok": True, "score": ev.score, "label": ev.label}


# ---------------------------------------------------------------------------
# GET /stats — time-bucketed averages for charts
# ---------------------------------------------------------------------------

@app.get("/stats")
def get_stats(bucket_min: int = 5):
    db = _sqlite()
    rows = db.execute("""
        SELECT
            strftime('%Y-%m-%dT%H:%M:00', ts) AS bucket,
            ROUND(AVG(score), 1) AS avg_score,
            COUNT(*) AS n
        FROM events
        WHERE ts > datetime('now', '-1 day')
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

@app.get("/tasks")
def get_tasks():
    db = _sqlite()
    rows = db.execute("SELECT * FROM tasks ORDER BY priority, created_ts").fetchall()
    db.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /events  GET /timeline
# ---------------------------------------------------------------------------

@app.get("/events")
def get_events(limit: int = 200):
    db = _sqlite()
    rows = db.execute(
        "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.get("/timeline")
def get_timeline(limit: int = 200):
    return get_events(limit)


# ---------------------------------------------------------------------------
# GET /journal
# ---------------------------------------------------------------------------

@app.get("/journal", response_class=Response)
def get_journal():
    today = datetime.now().strftime("%-d %b %Y") if os.name != "nt" else datetime.now().strftime("%#d %b %Y")
    db = _sqlite()
    tasks = db.execute("SELECT title, status, deadline FROM tasks ORDER BY priority").fetchall()
    incidents = db.execute(
        "SELECT ts, app, score, spoken_text FROM incidents ORDER BY ts"
    ).fetchall()
    stats = db.execute("SELECT ROUND(AVG(score),1) AS avg FROM events WHERE ts > datetime('now','-1 day')").fetchone()
    db.close()

    lines = [f"# Buddy journal — {today}", "", "## Goals"]
    for t in tasks:
        status = "~~" if t["status"] == "done" else ""
        deadline = f" (deadline {t['deadline']})" if t["deadline"] else ""
        lines.append(f"- {status}{t['title']}{deadline}{status}")

    lines += ["", "## Incidents"]
    if incidents:
        for inc in incidents:
            ts_str = inc["ts"][:16] if inc["ts"] else "unknown"
            lines.append(f"- {ts_str} — {inc['app']} (score {inc['score']}). {inc['spoken_text'] or ''}")
    else:
        lines.append("- No incidents today.")

    avg = stats["avg"] if stats and stats["avg"] else "—"
    lines += ["", f"## Day score: {avg}/100", "", "## Suggestion"]
    lines.append("_Generated by Buddy._")

    return Response(content="\n".join(lines), media_type="text/markdown")


# ---------------------------------------------------------------------------
# POST /coach
# ---------------------------------------------------------------------------

class CoachRequest(BaseModel):
    tasks: list[str] = []
    now: str = ""
    current_app: str = ""
    score: int = 0
    unproductive_streak_s: int = 0
    last_productive_app: str = ""


@app.post("/coach")
def post_coach(req: CoachRequest):
    tasks = _get_tasks_for_gemini()
    try:
        text = _gemini_coach(req.dict(), tasks)
    except Exception:
        text = "You have work to finish. Get back to it."

    try:
        wav = speak_wav(text)
    except Exception:
        wav = _load_canned("off_task.wav")

    _speech_queue.put(wav)

    # Log incident
    db = _sqlite()
    db.execute(
        "INSERT INTO incidents(ts,kind,summary,spoken_text,app,score) VALUES(?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), "slump", f"{req.current_app} for {req.unproductive_streak_s}s",
         text, req.current_app, req.score),
    )
    db.commit()
    db.close()

    return {"ok": True, "spoken": text}


# ---------------------------------------------------------------------------
# GET /pending-speech — watch polls every 2 s
# ---------------------------------------------------------------------------

@app.get("/pending-speech")
def pending_speech():
    try:
        wav = _speech_queue.get_nowait()
        return Response(content=wav, media_type="audio/wav")
    except queue.Empty:
        return Response(status_code=204)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_canned(name: str) -> bytes:
    p = pathlib.Path(__file__).parent.parent / "audio" / name
    if p.exists():
        return p.read_bytes()
    return b""
