"""The user's running productivity score: one number between 0 and 1.

The classifier votes, time decides how loudly. Each scored activity arrives as a verdict of
1 (productive) or 0 (unproductive), and pulls the score that way by an amount set only by how
long the activity lasted:

    alpha = 1 - exp(-seconds / TAU)
    score = score + alpha * (target - score)

The update is a weighted average between the old score and the new verdict, so the result can
never leave 0-1 - no clamping, no drift. 0.7 means "roughly 70% of your recent time was spent
on things the model called productive". A 30-second glance barely moves it; twenty minutes
moves it most of the way. TAU is the memory: at 5 minutes, half an hour ago has almost no
say left.

Nothing is persisted here - the score rides along on every activity row as score_after, so the
database already holds its whole history.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from engine.config import SCORE_START, SCORE_TAU_SECONDS


@dataclass
class ScoreUpdate:
    before: float
    after: float
    counted_s: float


class ScoreKeeper:
    def __init__(self, start: float = SCORE_START, tau_s: float = SCORE_TAU_SECONDS) -> None:
        self.tau_s = tau_s
        self.value = start
        self.updated_at: str | None = None

    def resume_from(self, value: float | None) -> None:
        """Pick up where the last stored activity left off."""
        if value is not None:
            self.value = float(value)

    def apply(self, target: float, seconds: float, at: datetime) -> ScoreUpdate:
        """target is the classifier's verdict: 1.0 productive, 0.0 unproductive."""
        before = self.value
        if seconds > 0:
            alpha = 1.0 - math.exp(-seconds / self.tau_s)
            self.value = before + alpha * (target - before)
            self.updated_at = at.isoformat()
        return ScoreUpdate(round(before, 4), round(self.value, 4), round(seconds, 2))

    def as_dict(self) -> dict:
        return {"score": round(self.value, 3), "updated_at": self.updated_at,
                "tau_minutes": round(self.tau_s / 60, 1)}
