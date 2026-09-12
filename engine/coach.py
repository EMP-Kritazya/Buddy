"""Turns the engine's numbers into one spoken sentence.

Gemini when a key is present, a canned line when it is not - the demo must still talk if the
venue wifi dies.
"""
from __future__ import annotations

import logging
import os
import random

log = logging.getLogger("uvicorn.error")

PROMPT = """You are Buddy, a desk mentor that speaks out loud through a small device.
The user has been off-task. Say ONE short line, at most 25 spoken words.

Rules:
- Talk like a friend who noticed, not a productivity app. No greetings, no sign-off.
- Name what they are actually doing, using the site below.
- End with one concrete next action, small enough to start right now.
- No guilt, no exclamation marks, no emoji, no medical or mental-health advice.

Last {window} minutes: productivity {score:.0%}, off task for {streak:.0f} seconds.
Where the time went: {where}.
"""


def build_context(state) -> dict:
    where = ", ".join(f"{t['name']} {t['seconds']:.0f}s" for t in state.top[:3]) or "unknown"
    return {"score": state.score or 0.0, "streak": state.streak_s, "where": where,
            "window": int(__import__("engine.config", fromlist=["x"]).WINDOW_MINUTES),
            "top_domain": state.top[0]["name"] if state.top else "that"}


def generate(context: dict) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        try:
            from google import genai

            client = genai.Client(api_key=key)
            reply = client.models.generate_content(
                model="gemini-2.5-flash", contents=PROMPT.format(**context)
            )
            text = (reply.text or "").strip().strip('"')
            if text:
                return text
        except Exception as exc:
            log.warning("coach: gemini unavailable (%s), using a canned line", exc)
    return canned(context)


def canned(context: dict) -> str:
    site = context["top_domain"]
    return random.choice([
        f"You've been on {site} for a while now. Pick one small thing and start it.",
        f"That's a few minutes of {site}. What were you supposed to be doing?",
        f"Still on {site}. Close it and give the next task ten minutes.",
    ])
