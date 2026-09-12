"""Activity store. JSONL today, TigerData/Timescale later - swapping means rewriting this file
and nothing else.

sessions.jsonl is append-only: a session is written once per heartbeat and again when it ends,
every row sharing a session_id. The newest row for an id wins, which is exactly the upsert the
database will do natively. The collapse is kept in memory so the loop never rescans the file.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine.config import CHECKINS_FILE, SCORES_FILE, SESSIONS_FILE


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class Store:
    def __init__(
        self,
        sessions_file: Path = SESSIONS_FILE,
        scores_file: Path = SCORES_FILE,
        checkins_file: Path = CHECKINS_FILE,
    ) -> None:
        self.sessions_file = sessions_file
        self.scores_file = scores_file
        self.checkins_file = checkins_file
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}  # session_id -> newest row
        self._scores: dict[str, dict] = {}    # session_id -> score row
        self._checkins: list[dict] = []
        self._load()

    def _load(self) -> None:
        for path, sink in ((self.sessions_file, self._sessions), (self.scores_file, self._scores)):
            for row in _read_jsonl(path):
                if "session_id" in row:
                    sink[row["session_id"]] = row
        self._checkins = list(_read_jsonl(self.checkins_file))

    # ------------------------------------------------------------------ writes
    def append_sessions(self, rows: list[dict]) -> list[dict]:
        """Persist rows and return those that need scoring: a session seen for the first time,
        or one whose final row arrived after it was scored from a provisional title."""
        needs_score = []
        with self._lock:
            with self.sessions_file.open("a", encoding="utf-8") as f:
                for row in rows:
                    sid = row["session_id"]
                    scored = self._scores.get(sid)
                    if scored is None or (row.get("is_final") and not scored.get("from_final")):
                        needs_score.append(row)
                    self._sessions[sid] = row
                    f.write(json.dumps(row) + "\n")
        return needs_score

    def save_score(self, session_id: str, score: dict) -> None:
        row = {"session_id": session_id, **score}
        with self._lock:
            self._scores[session_id] = row
            with self.scores_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

    def append_checkin(self, entry: dict) -> None:
        with self._lock:
            self._checkins.append(entry)
            with self.checkins_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------- reads
    def scored_since(self, since: datetime) -> list[dict]:
        """Collapsed sessions overlapping `since`, each with its score attached."""
        out = []
        with self._lock:
            rows = list(self._sessions.values())
            scores = dict(self._scores)
        for row in rows:
            if parse_ts(row["end_ts"]) < since:
                continue
            score = scores.get(row["session_id"], {})
            out.append({**row, "p": score.get("p"), "label": score.get("label"),
                        "score_source": score.get("source")})
        return sorted(out, key=lambda r: parse_ts(r["start_ts"]))

    def last_activity_at(self) -> datetime | None:
        with self._lock:
            rows = list(self._sessions.values())
        return max((parse_ts(r["end_ts"]) for r in rows), default=None)

    def last_checkin_at(self) -> datetime | None:
        with self._lock:
            return parse_ts(self._checkins[-1]["ts"]) if self._checkins else None

    def recent_checkins(self, limit: int = 10) -> list[dict]:
        with self._lock:
            return self._checkins[-limit:]

    def counts(self) -> dict:
        with self._lock:
            return {"sessions": len(self._sessions), "scored": len(self._scores),
                    "checkins": len(self._checkins)}


def _read_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
