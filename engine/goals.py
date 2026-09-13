"""Goals: what the user meant to do today, and what they finished.

Thin over engine.db - every query lives there, so this file is only shape and validation. A
goal carrying match_terms is measured against the activity table rather than self-reported,
which is why `minutes_spent` comes back on every read without anyone updating anything.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from engine import db

router = APIRouter(prefix="/goals", tags=["goals"])


class NewGoal(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    target_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    # Domains or app names that count toward this goal, e.g. ["github.com", "Code"].
    # Leave empty for a goal with nothing to measure, like "call home".
    match_terms: list[str] | None = None
    priority: int = 0
    source: str = "user"          # 'buddy' when Gemini proposes one
    goal_date: date | None = None


class Completion(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get("")
async def list_goals(request: Request, day: date | None = None) -> list[dict]:
    """Today's goals, each with minutes spent so far and whether it was finished."""
    return await db.goals_for(request.app.state.pool, day)


@router.post("")
async def create_goal(goal: NewGoal, request: Request) -> dict:
    """Add a goal. Re-posting the same title on the same day updates it instead of duplicating."""
    return await db.add_goal(
        request.app.state.pool, title=goal.title, target_minutes=goal.target_minutes,
        match_terms=goal.match_terms, priority=goal.priority, source=goal.source,
        day=goal.goal_date)


@router.post("/{goal_id}/complete")
async def complete(goal_id: int, request: Request, body: Completion | None = None) -> dict:
    """Tick a goal off, recording the minutes actually spent and the score at that moment."""
    row = await db.complete_goal(request.app.state.pool, goal_id,
                                 score=request.app.state.keeper.value,
                                 note=body.note if body else None)
    if row is None:
        # Either there is no such goal, or it was already done - both mean "nothing changed".
        raise HTTPException(404, "no such goal, or already completed")
    return row


@router.delete("/{goal_id}/complete")
async def uncomplete(goal_id: int, request: Request) -> dict:
    """Untick a goal."""
    if not await db.uncomplete_goal(request.app.state.pool, goal_id):
        raise HTTPException(404, "that goal was not completed")
    return {"goal_id": goal_id, "completed": False}


@router.delete("/{goal_id}")
async def remove(goal_id: int, request: Request) -> dict:
    if not await db.delete_goal(request.app.state.pool, goal_id):
        raise HTTPException(404, "no such goal")
    return {"goal_id": goal_id, "deleted": True}


@router.get("/completed")
async def completed(request: Request, day: date | None = None) -> list[dict]:
    """What was finished on a given day - what Gemini reads to give credit."""
    return await db.completed_on(request.app.state.pool, day)


@router.post("/carry-over")
async def carry_over(request: Request, to_day: date | None = None) -> dict:
    """Roll yesterday's unfinished goals into today, remembering where each came from."""
    moved = await db.carry_over(request.app.state.pool, to_day)
    return {"carried": moved}


@router.get("/progress")
async def progress(request: Request, day: date | None = None) -> dict:
    """The whole day in one object - what a dashboard header needs."""
    goals = await db.goals_for(request.app.state.pool, day)
    done = [g for g in goals if g["completed_at"]]
    measured = [g for g in goals if g["target_minutes"]]
    return {
        "date": (day or date.today()).isoformat(),
        "total": len(goals),
        "completed": len(done),
        "target_minutes": sum(g["target_minutes"] for g in measured),
        "minutes_spent": round(sum(float(g["minutes_spent"]) for g in measured), 1),
        "score_now": round(request.app.state.keeper.value, 3),
    }
