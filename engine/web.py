"""The dashboard's API: /api/* , shaped exactly the way the frontend already expects.

This is a TRANSLATION layer and nothing else. Every number here comes from db.py or from the
running engine state; no scoring, no triggering, no goal rules live in this file. The frontend
was built against its own contract, so rather than rewrite eight services this maps that
contract onto what the engine already stores.

The engine's own endpoints (/score, /timeline, /goals, /ingest, /pending-speech) are untouched
and keep serving the extension, the watch and MATLAB.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from engine import db, matlab, voice
from engine.config import LOCAL_TZ
from engine.store_helpers import now

router = APIRouter(prefix="/api", tags=["dashboard"])

TZ = ZoneInfo(LOCAL_TZ)


def local_day(day: date | None = None) -> tuple[datetime, datetime]:
    """Midnight-to-midnight in the user's zone, as UTC-aware bounds."""
    d = day or datetime.now(TZ).date()
    start = datetime.combine(d, time.min, tzinfo=TZ)
    return start, start + timedelta(days=1)


def trigger_for(score: float | None) -> int:
    """0 focused, 1 drifting, 2 distracted.

    Mirrors the frontend's own triggerFromScore() thresholds so a value the API supplies and
    one the UI derives can never disagree.
    """
    if score is None:
        return 0
    display = round(score * 100 if score <= 1 else score)
    if display > 70:
        return 0
    return 1 if display >= 50 else 2


def _samples(points: list[dict]) -> list[dict]:
    return [{"timestamp": p["ts"].isoformat(), "score": round(p["score"], 4),
             "trigger": trigger_for(p["score"])} for p in points]


# --- scores ---------------------------------------------------------------------------------

@router.get("/scores/current")
async def scores_current(request: Request) -> dict:
    """What the user is doing right now, and how it is going."""
    state = request.app.state
    row = await db.latest_activity(state.pool)
    score = float(state.keeper.value)
    last = matlab.state()["last_trigger"]
    return {
        "score": round(score, 4),
        "app_name": (row or {}).get("domain") or (row or {}).get("app_name") or "",
        "window_title": (row or {}).get("title") or "",
        "session_duration": round(float((row or {}).get("duration_s") or 0)),
        # MATLAB's own verdict when it is fresh; otherwise fall back to the score itself, so
        # the dial is never blank just because MATLAB has not spoken yet.
        "trigger": last["level"] if last else trigger_for(score),
    }


@router.get("/scores/live")
async def scores_live(request: Request, minutes: int = 60) -> list[dict]:
    """The last hour of score points - the live graph."""
    return _samples(await db.score_series(request.app.state.pool,
                                          now() - timedelta(minutes=minutes)))


@router.get("/scores/today")
async def scores_today(request: Request) -> list[dict]:
    """Every score point since local midnight."""
    start, end = local_day()
    return _samples(await db.score_series(request.app.state.pool, start, end))


# --- the day --------------------------------------------------------------------------------

@router.get("/summary/today")
async def summary_today(request: Request) -> dict:
    start, end = local_day()
    pool = request.app.state.pool
    stats = await db.day_stats(pool, start, end)
    goals = await db.goals_for(pool)
    best = stats["best_hour"]
    return {
        "focus_time_mins": round(stats["tracked_s"] / 60, 1),
        "avg_score": round(stats["avg_p"], 4),
        "incidents": stats["slumps"],
        "tasks_completed": sum(1 for g in goals if g["completed_at"]),
        "tasks_total": len(goals),
        "strongest_period": f"{best:%H:%M}-{best + timedelta(hours=1):%H:%M}" if best else "",
        # Both of these are Gemini prose, and this endpoint is polled. Generating on every poll
        # would burn the daily quota in an hour, so they stay empty until asked for explicitly.
        "gemini_reflection": "",
        "tomorrow_suggestion": "",
    }


# --- tasks (the engine calls them goals) ----------------------------------------------------

def _status(goal: dict) -> str:
    if goal["completed_at"]:
        return "done"
    spent = float(goal["minutes_spent"] or 0)
    if goal["target_minutes"] and spent >= goal["target_minutes"]:
        return "in_progress"          # target met but not ticked off
    return "in_progress" if spent > 0 else "todo"


def _task(goal: dict) -> dict:
    # Goals are day-scoped with a minute target, not deadlines, so `due` says WHICH DAY rather
    # than inventing a clock time the user never gave us.
    today = datetime.now(TZ).date()
    when = goal["goal_date"]
    due = ("today" if when == today
           else "tomorrow" if when == today + timedelta(days=1)
           else when.strftime("%a %d %b"))
    if goal["target_minutes"]:
        due = f"{due} - {goal['target_minutes']} min"
    return {"id": str(goal["id"]), "title": goal["title"],
            "due": due, "status": _status(goal)}


@router.get("/tasks/today")
async def tasks_today(request: Request) -> list[dict]:
    return [_task(g) for g in await db.goals_for(request.app.state.pool)]


@router.get("/tasks/current")
async def tasks_current(request: Request) -> dict | None:
    """The highest-priority unfinished goal, with how much of its target is left."""
    goals = [g for g in await db.goals_for(request.app.state.pool) if not g["completed_at"]]
    if not goals:
        return None
    goal = goals[0]                    # goals_for() already orders by priority, then id
    target = goal["target_minutes"] or 0
    spent = float(goal["minutes_spent"] or 0)
    return {**_task(goal), "minutes_left": max(round(target - spent), 0)}


@router.get("/tasks/tomorrow")
async def tasks_tomorrow(request: Request) -> list[dict]:
    rows = await db.goals_for(request.app.state.pool, date.today() + timedelta(days=1))
    return [{"id": str(g["id"]), "title": g["title"],
             "priority": "high" if g["priority"] > 0 else "medium"} for g in rows]


class NewTask(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: str = "medium"


@router.post("/tasks/tomorrow")
async def add_tomorrow(task: NewTask, request: Request) -> dict:
    row = await db.add_goal(request.app.state.pool, title=task.title,
                            priority=1 if task.priority == "high" else 0,
                            day=date.today() + timedelta(days=1))
    return {"id": str(row["id"]), "title": row["title"], "priority": task.priority}


class TaskUpdate(BaseModel):
    status: str


@router.patch("/tasks/{task_id}")
async def update_task(task_id: int, body: TaskUpdate, request: Request) -> dict:
    pool = request.app.state.pool
    if body.status == "done":
        row = await db.complete_goal(pool, task_id, score=request.app.state.keeper.value)
        if row is None:
            raise HTTPException(404, "no such task, or already done")
    else:
        await db.uncomplete_goal(pool, task_id)
    return {"id": str(task_id), "status": body.status}


# --- the watch ------------------------------------------------------------------------------

@router.get("/wearable/status")
async def wearable_status() -> dict:
    v = voice.state()
    last = v["last"]
    return {
        "connected": voice.seen_recently(),
        "last_trigger_time": last["at"] if last and last.get("at") else "",
        "last_trigger_message": last["text"] if last else "",
    }


# --- what Buddy said today ------------------------------------------------------------------
# All three of these read the same `nudge` rows; they differ only in the shape each screen wants.

@router.get("/incidents/today")
async def incidents_today(request: Request) -> list[dict]:
    """Every time Buddy stepped in today, and what it said."""
    start, end = local_day()
    rows = await db.nudges_between(request.app.state.pool, start, end)
    return [{
        "id": str(r["id"]),
        "timestamp": r["at"].isoformat(),
        "app_name": r["domain"] or "",
        "duration_secs": round(float(r["duration_s"] or 0)),
        "score": round(float(r["score"] or 0), 4),
        "trigger": r["level"],
        # "intervened" means the user actually heard it - a nudge whose audio never rendered
        # was a decision, not an intervention.
        "intervened": r["spoken"],
        "gemini_response": r["text"],
    } for r in rows]


@router.get("/wearable/messages")
async def wearable_messages(request: Request) -> list[dict]:
    """What came out of the speaker today, newest first."""
    start, end = local_day()
    rows = await db.nudges_between(request.app.state.pool, start, end)
    return [{
        "time": r["at"].astimezone(TZ).strftime("%H:%M"),
        "message": r["text"],
        "type": "hard" if r["level"] == matlab.HARD else "soft",
    } for r in reversed(rows) if r["spoken"]]


@router.get("/gemini/commentary")
async def commentary(request: Request) -> list[dict]:
    """The day as a running commentary - one entry per thing Buddy said."""
    start, end = local_day()
    rows = await db.nudges_between(request.app.state.pool, start, end)
    return [{
        "id": str(r["id"]),
        "time": r["at"].astimezone(TZ).strftime("%H:%M"),
        "period": None,
        "text": r["text"],
        "type": "incident" if r["level"] == matlab.HARD else "warning",
    } for r in rows]


# --- the user -------------------------------------------------------------------------------

class Onboarding(BaseModel):
    """Exactly the shape the frontend's onboardingService already builds."""
    name: str = Field(min_length=1, max_length=120)
    email: str = ""
    university: str = ""
    major: str = ""
    level: str = ""
    studyHours: str = ""
    peakTime: str = ""
    distraction: str = ""
    needs: list[str] = []
    goal: str = ""


@router.post("/users/onboarding")
async def onboarding(body: Onboarding, request: Request) -> dict:
    """Save who the user is. Gemini is handed the name and standing goal on every call."""
    saved = await db.save_profile(request.app.state.pool, {
        "name": body.name, "email": body.email or None, "university": body.university,
        "major": body.major, "level": body.level, "study_hours": body.studyHours,
        "peak_time": body.peakTime, "distraction": body.distraction,
        "needs": body.needs, "goal": body.goal,
    })
    return {"success": True, "name": saved["name"], "goal": saved["goal"]}


class Fix(BaseModel):
    """One location fix from the browser, i.e. where this laptop is."""
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = None


@router.post("/users/location")
async def location(fix: Fix, request: Request) -> dict:
    """Where the laptop is, read by the browser and kept on the profile.

    The engine cannot determine this itself - no GPS, macOS removed the Wi-Fi scanning tools,
    and an IP lookup only resolves to the city. The browser can, so it tells us.
    """
    await db.save_location(request.app.state.pool, fix.lat, fix.lng, fix.accuracy_m)
    return {"ok": True}


@router.get("/users/profile")
async def profile(request: Request) -> dict:
    """One local user, so there is no account to look up - just whoever finished onboarding."""
    row = await db.get_profile(request.app.state.pool)
    if row is None:
        return {"id": "local", "name": "", "email": None, "onboarded": False}
    return {
        "id": "local", "name": row["name"], "email": row["email"],
        "university": row["university"], "major": row["major"], "level": row["level"],
        "studyHours": row["study_hours"], "peakTime": row["peak_time"],
        "distraction": row["distraction"], "needs": row["needs"] or [],
        "goal": row["goal"], "onboarded": True,
    }
