# Appending to sessions.jsonl


from __future__ import annotations

import json

from engine.config import SESSIONS_FILE


def append(rows: list[dict]) -> None:
    with SESSIONS_FILE.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
