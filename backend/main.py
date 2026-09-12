"""
Buddy mock backend — full voice loop for the watch demo.

Watch PCM -> ElevenLabs STT -> Gemini reply -> ElevenLabs TTS WAV -> watch speaker.
Keys from D:\\Buddy\\.env (GEMINI_API_KEY, ELEVENLABS_API_KEY).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import wave
from collections import deque
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

from voice.eleven import speak_wav, transcribe  # noqa: E402

import google.generativeai as genai  # noqa: E402

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    _model = genai.GenerativeModel(
        model_name=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
        system_instruction=(
            "You are Buddy, a concise productivity coach on a wrist speaker. "
            "The user speaks goals and questions. "
            "Return ONLY compact JSON with keys: "
            "reply (string, spoken aloud, under 20 seconds when read), "
            "tasks_add (array of {title, deadline, priority, estimate_min}), "
            "tasks_update (array of {id, status}). "
            "Prefer the shortest task first when they dump several goals. "
            "No medical advice. No markdown. No code fences."
        ),
    )
else:
    print("[warn] GEMINI_API_KEY empty in .env — /voice will STT+TTS without Gemini until you set it")

app = FastAPI(title="Buddy mock backend")
app.mount("/audio", StaticFiles(directory=str(ROOT / "audio")), name="audio")
_pending: deque[bytes] = deque()
_tasks: list[dict] = []


def pcm16_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _looks_like_wav(data: bytes) -> bool:
    return len(data) > 44 and data[0:4] == b"RIFF" and data[8:12] == b"WAVE"


def _canned(name: str) -> bytes | None:
    path = ROOT / "audio" / name
    return path.read_bytes() if path.exists() else None


def _parse_gemini_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"reply": text[:300] or "Okay.", "tasks_add": [], "tasks_update": []}


def gemini_buddy(user_text: str) -> dict:
    if _model is None:
        raise RuntimeError("GEMINI_API_KEY not set")
    task_ctx = json.dumps(_tasks[-10:], ensure_ascii=False)
    prompt = (
        f"Current open tasks (JSON): {task_ctx}\n"
        f"User said: {user_text}\n"
        "Respond with JSON only."
    )
    result = _model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.4,
            "response_mime_type": "application/json",
        },
    )
    data = _parse_gemini_json(getattr(result, "text", "") or "")
    if not isinstance(data.get("reply"), str) or not data["reply"].strip():
        data["reply"] = "Got it."
    data.setdefault("tasks_add", [])
    data.setdefault("tasks_update", [])
    return data


def _apply_tasks(data: dict) -> None:
    for t in data.get("tasks_add") or []:
        if not isinstance(t, dict):
            continue
        title = str(t.get("title") or "").strip()
        if not title:
            continue
        item = {
            "id": f"task_{len(_tasks)+1}",
            "title": title,
            "deadline": t.get("deadline"),
            "priority": t.get("priority", 1),
            "estimate_min": t.get("estimate_min"),
            "status": "open",
        }
        _tasks.append(item)
        print("[tasks] add", item)
    for u in data.get("tasks_update") or []:
        if not isinstance(u, dict):
            continue
        tid = u.get("id")
        for item in _tasks:
            if item.get("id") == tid:
                if "status" in u:
                    item["status"] = u["status"]
                print("[tasks] update", item)


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "buddy-mock",
        "gemini": bool(GEMINI_API_KEY),
        "eleven": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "tasks": len(_tasks),
    }


@app.post("/voice")
async def voice(request: Request):
    """PCM16@16kHz (or WAV) in -> STT -> Gemini -> TTS WAV out."""
    body = await request.body()
    if not body:
        return Response(status_code=400, content=b"empty body")

    wav_in = body if _looks_like_wav(body) else pcm16_to_wav(body)

    try:
        text = (transcribe(wav_in) or "").strip()
    except Exception as exc:
        print("[voice] STT failed:", exc)
        fallback = _canned("goals_ok.wav")
        if fallback:
            return Response(content=fallback, media_type="audio/wav")
        return Response(status_code=502, content=b"stt failed")

    print("[voice] heard:", text)
    # Scribe often returns tags like [background noise] when mic is quiet
    if text and re.fullmatch(r"\[[^\]]+\]", text):
        print("[voice] ignoring noise-only transcript")
        text = ""
    if not text:
        reply = "I didn't catch that. Tap again and speak a little louder."
        data = {"reply": reply, "tasks_add": [], "tasks_update": []}
    else:
        try:
            data = gemini_buddy(text)
        except Exception as exc:
            print("[voice] Gemini failed:", exc)
            data = {
                "reply": f"I heard you say: {text[:120]}. Gemini is unavailable right now.",
                "tasks_add": [],
                "tasks_update": [],
            }

    _apply_tasks(data)
    reply = str(data.get("reply") or "Okay.").strip()
    print("[voice] reply:", reply)

    try:
        wav_out = speak_wav(reply)
    except Exception as exc:
        print("[voice] TTS failed:", exc)
        fallback = _canned("goals_ok.wav")
        if fallback:
            return Response(content=fallback, media_type="audio/wav")
        return Response(status_code=502, content=b"tts failed")

    return Response(content=wav_out, media_type="audio/wav")


@app.get("/pending-speech")
def pending_speech():
    if not _pending:
        return Response(status_code=204)
    return Response(content=_pending.popleft(), media_type="audio/wav")


@app.post("/coach")
async def coach(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    line = payload.get("spoken") or payload.get("reply")
    if not line:
        try:
            data = gemini_buddy(
                "Give one short spoken coaching nudge. Context: "
                + json.dumps(payload)[:500]
            )
            line = data.get("reply")
        except Exception:
            line = "You have work left. Get back to the project."
    try:
        _pending.append(speak_wav(str(line)[:240]))
    except Exception as exc:
        print("[coach] TTS failed:", exc)
        fb = _canned("off_task.wav")
        if fb:
            _pending.append(fb)
    return {"ok": True, "queued": len(_pending), "spoken": line}


@app.get("/tasks")
def tasks():
    return [t for t in _tasks if t.get("status", "open") == "open"]


@app.post("/events")
async def events(request: Request):
    data = await request.json()
    print("[events]", data.get("app"), data.get("score"))
    return {"ok": True}


@app.get("/events")
@app.get("/stats")
@app.get("/timeline")
def empty_list():
    return []


@app.get("/journal")
def journal():
    lines = ["# Buddy journal", "## Goals"]
    for t in _tasks:
        lines.append(f"- {t.get('title')} ({t.get('status')})")
    return Response(content="\n".join(lines) + "\n", media_type="text/markdown")
