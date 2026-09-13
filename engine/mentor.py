"""

    matlab.Trigger  ->  gather_context()  ->  compose()  ->  speak()
                        (read the db)        (Gemini)        (ElevenLabs -> ESP32)

"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpg

from engine import db, voice
from engine.config import (GEMINI_API_KEY, GEMINI_MAX_TOKENS, GEMINI_MODEL,
                           GEMINI_TEMPERATURE, GEMINI_THINKING)
from engine.matlab import HARD, SOFT, Trigger
from engine.store_helpers import now

try:
    from google import genai
    from google.genai import errors, types
except ImportError:      # the engine still runs without it; Buddy just stays quiet
    genai = None

log = logging.getLogger("uvicorn.error")

# Who Buddy is. Sent as a system instruction rather than glued onto the prompt, so the facts in
# build_prompt() stay separate from the character - you can iterate on either alone.
PERSONA = """You are Buddy, a productivity mentor who speaks out loud through a small speaker.
Rules:
- One or two short sentences. Never more. This is being read aloud.
- Name the specific thing they are doing or avoiding. Use the data you are given.
- Never scold, never guilt, never moralise. You are a friend, not a manager.
- No greetings, no sign-offs, no emoji, no markdown. Just the line you would say."""

# The watch button is a conversation, not an interruption - so it gets a little more room and
# is allowed to answer a question rather than only redirect.
ANSWER_PERSONA = """You are Buddy, a productivity mentor answering out loud through a speaker.
Rules:
- Two or three short sentences at most. This is being read aloud.
- Answer what they actually asked, using the data given. Be concrete about times and goals.
- Never scold, never guilt. You are a friend, not a manager.
- No greetings, no sign-offs, no emoji, no markdown."""

# Built on first use and kept: constructing a client per nudge is pure overhead.
_client = None

CONTEXT_HOURS = 2.0

_last: Nudge | None = None   # what Buddy said most recently, for /health and the UI


@dataclass
class Nudge:
    """One thing Buddy says, and the evidence behind it."""
    text: str
    level: int          # the MATLAB level that prompted it: 1 soft, 2 hard
    reason: str         # MATLAB's own words
    score: float
    at: datetime


# --- the pipeline --------------------------------------------------------------------------

async def handle(trigger: Trigger, pool: asyncpg.Pool) -> Nudge | None:
    """Run the three steps. Registered with matlab.set_handler() at startup.

    Returns the Nudge that was spoken, or None if Buddy decided to stay quiet.
    """
    global _last

    context = await gather_context(trigger, pool)

    text = await compose(trigger, context)
    if not text:
        log.info("mentor: nothing to say")
        return None

    nudge = Nudge(text=text, level=trigger.level, reason=trigger.reason,
                  score=trigger.score, at=now())
    log.warning("mentor: %s", text)

    await speak(nudge)
    _last = nudge
    return nudge


async def gather_context(trigger: Trigger, pool: asyncpg.Pool) -> dict:
    """Pull the facts Gemini needs to say something specific rather than generic.

    `summary()` already returns tracked/productive minutes and the top places by time, which is
    most of what a good nudge needs - what they have been doing, and for how long.

    TODO: add whatever else the prompt wants. Candidates:
      - the current goal, once the goals table exists
      - how today compares to this hour yesterday
      - whether this is the first nudge of the day or the fourth
    """
    since = now() - timedelta(hours=CONTEXT_HOURS)
    todays_goals = await db.goals_for(pool)
    good_summary = await db.summary(pool, since)
    return {
        "trigger_level": trigger.level,          # 1 soft, 2 hard
        "trigger_reason": trigger.reason,        # e.g. "above 0.5 but dropping 3 consecutive"
        "score_now": trigger.score,
        "hours": CONTEXT_HOURS,
        "totals": good_summary["totals"],             # tracked / productive seconds, session count
        "places": good_summary["places"],             # [{name, seconds, p}, ...] biggest first
        # What they meant to do today. This is what lets a nudge be specific - "you are 40
        # minutes short on the wiring" rather than a generic "get back to work".
        "goals_open": [_goal_brief(g) for g in todays_goals if not g["completed_at"]],
        "goals_done": [g["title"] for g in todays_goals if g["completed_at"]],
    }


def _goal_brief(goal: dict) -> dict:
    """Just enough of a goal for a prompt: what it is, and how far off it is."""
    return {"title": goal["title"],
            "target_minutes": goal["target_minutes"],
            "minutes_spent": round(float(goal["minutes_spent"]), 1),
            "carried_from": goal["carried_from"].isoformat() if goal["carried_from"] else None}


async def compose(trigger: Trigger, context: dict) -> str | None:
    return await _generate(build_prompt(trigger, context), PERSONA)


# --- conversation memory -------------------------------------------------------------------
# The watch is one device with one user, so a single rolling window is enough. Only the plain
# question and answer are kept, never the data-heavy prompt - history should stay cheap, and
# yesterday's activity numbers would be wrong to replay anyway.
#
# The deque is a cache, not the record: every exchange is also written to the conversation
# table, and prime() refills this from there at startup. Restarting the engine no longer costs
# Buddy its memory.
HISTORY_TURNS = 6
_history: deque = deque(maxlen=HISTORY_TURNS * 2)


def prime(turns: list[tuple[str, str]]) -> None:
    """Refill the window from the database. Called once from the app lifespan."""
    _history.clear()
    for role, text in turns[-HISTORY_TURNS * 2:]:
        _history.append(types.Content(role=role, parts=[types.Part(text=text)]))
    if _history:
        log.info("mentor: recalled %d spoken turn(s)", len(_history))

# A goal the user has stated but not yet confirmed out loud. Lives here, not in the database:
# an unconfirmed goal is not a goal.
_pending_goal: dict | None = None


async def forget(pool=None) -> None:
    """Drop the conversation and any half-set goal, from memory and from the database."""
    global _pending_goal
    _history.clear()
    _pending_goal = None
    if pool is not None:
        async with pool.acquire() as conn:
            await conn.execute("delete from conversation")


def conversation() -> list[dict]:
    """What /health shows, so you can see what Buddy thinks was said."""
    return [{"role": c.role, "text": c.parts[0].text} for c in _history]


# --- tools Gemini can call -----------------------------------------------------------------
# The two-step confirm lives in these descriptions rather than in ANSWER_PERSONA, so the
# persona stays exactly as written.

def _tools():
    return [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="propose_goal",
            description=(
                "Call this the moment the user states something they want to get done today. "
                "It does NOT save anything. After calling it you MUST read the goal back to "
                "the user and ask them to confirm, e.g. 'Set finish the report as today's "
                "goal?'. Only save it once they say yes."),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(
                        type=types.Type.STRING,
                        description="The goal in the user's own words, short and concrete."),
                    "target_minutes": types.Schema(
                        type=types.Type.INTEGER,
                        description="Minutes they intend to spend, if they said. Omit if not."),
                    "match_terms": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description=(
                            "Website domains or desktop app names whose usage should count "
                            "toward this goal, e.g. ['github.com', 'Code']. Only include ones "
                            "you are confident about; omit entirely if unsure.")),
                },
                required=["title"])),
        types.FunctionDeclaration(
            name="confirm_goal",
            description=(
                "Save the goal you proposed. Call this ONLY after the user has clearly agreed "
                "to it out loud. Never call it in the same turn as propose_goal."),
            parameters=types.Schema(type=types.Type.OBJECT, properties={})),
        types.FunctionDeclaration(
            name="cancel_goal",
            description="Discard the proposed goal, when the user declines or changes it.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})),
    ])]


async def _call_tool(name: str, args: dict, pool) -> dict:
    """Run one tool. The return value goes back to Gemini as the function response."""
    global _pending_goal
    if name == "propose_goal":
        _pending_goal = {"title": args["title"],
                         "target_minutes": args.get("target_minutes"),
                         "match_terms": args.get("match_terms")}
        log.info("mentor: goal proposed (awaiting confirmation) %r", _pending_goal["title"])
        return {"status": "awaiting_confirmation", **_pending_goal,
                "next": "Read the goal back and ask the user to confirm. Do not save it yet."}

    if name == "confirm_goal":
        if not _pending_goal:
            return {"status": "nothing_to_confirm",
                    "next": "Ask what they would like the goal to be."}
        saved = await db.add_goal(pool, title=_pending_goal["title"],
                                  target_minutes=_pending_goal["target_minutes"],
                                  match_terms=_pending_goal["match_terms"],
                                  source="buddy")
        log.warning("mentor: goal saved -> %r (id %s)", saved["title"], saved["id"])
        _pending_goal = None
        return {"status": "saved", "id": saved["id"], "title": saved["title"]}

    if name == "cancel_goal":
        _pending_goal = None
        return {"status": "cancelled"}
    return {"status": "unknown_tool"}


async def answer(question: str, pool) -> str | None:
    """Reply to something the user said into the watch microphone.

    Same model and voice, different job: this one is a conversation, so it may reference the
    goals and the day rather than nudging about them.
    """
    summary = await db.summary(pool, now() - timedelta(hours=CONTEXT_HOURS))
    goals = await db.goals_for(pool)
    prompt = (
        f"they asked: {question}\n"
        f"their productivity score right now: {await _score_hint(pool)}\n"
        f"last {CONTEXT_HOURS:.0f}h: {summary['totals']}\n"
        f"where the time went: {summary['places']}\n"
        f"still to do today: {[_goal_brief(g) for g in goals if not g['completed_at']]}\n"
        f"already finished: {[g['title'] for g in goals if g['completed_at']]}\n"
    )
    return await _converse(prompt, question, pool)


async def _converse(prompt: str, question: str, pool) -> str | None:
    """One spoken exchange: history + live data in, tool calls handled, spoken line out.

    Kept separate from _generate() because the nudge path wants neither memory nor tools - a
    trigger is a statement, not a conversation, and it must never be able to write to the
    database on its own.
    """
    if genai is None or not GEMINI_API_KEY:
        log.warning("mentor: no Gemini (%s) - staying quiet",
                    "package missing" if genai is None else "GEMINI_API not set in .env")
        return None

    contents = list(_history) + [types.Content(role="user", parts=[types.Part(text=prompt)])]
    config = types.GenerateContentConfig(
        system_instruction=ANSWER_PERSONA,
        max_output_tokens=GEMINI_MAX_TOKENS,
        temperature=GEMINI_TEMPERATURE,
        thinking_config=_thinking(),
        # We run the tool loop ourselves in _converse(), so the SDK's automatic path must be
        # off. Leaving it on is what prints the "Direct use of automatic function calling"
        # warning on every single call, even ones that declare no tools at all.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tools=_tools(),
    )

    # Rounds, not recursion: the model calls a tool, we answer it, the model speaks. Three is a
    # ceiling, not an expectation - it stops a model that keeps calling tools from looping.
    resp = None
    for _ in range(3):
        try:
            resp = await _gemini().aio.models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config)
        except errors.ClientError as exc:
            log.warning("mentor: gemini rejected the request (%s)", exc)
            return None
        except errors.ServerError as exc:
            log.warning("mentor: gemini unavailable (%s)", exc)
            return None
        except Exception as exc:
            log.warning("mentor: gemini call failed (%s: %s)", type(exc).__name__, exc)
            return None

        calls = resp.function_calls
        if not calls:
            break
        contents.append(resp.candidates[0].content)      # the model's tool call
        replies = []
        for call in calls:
            result = await _call_tool(call.name, dict(call.args or {}), pool)
            log.info("mentor: tool %s -> %s", call.name, result.get("status"))
            replies.append(types.Part.from_function_response(name=call.name, response=result))
        contents.append(types.Content(role="user", parts=replies))

    text = (resp.text or "").strip() if resp else ""
    if not text:
        log.warning("mentor: no spoken reply after tool handling")
        return None

    spoken = _for_speech(text)
    # Only the plain exchange is remembered - not the prompt, and not the tool traffic.
    _history.append(types.Content(role="user", parts=[types.Part(text=question)]))
    _history.append(types.Content(role="model", parts=[types.Part(text=spoken)]))
    try:
        await db.append_conversation(pool, [("user", question), ("model", spoken)])
    except Exception as exc:
        # Losing the written record costs memory across a restart, not this reply.
        log.warning("mentor: could not record the exchange (%s: %s)", type(exc).__name__, exc)
    return spoken


async def _score_hint(pool) -> str:
    score = await db.current_score(pool)
    return "unknown" if score is None else f"{score:.2f}"


async def _generate(prompt: str, persona: str) -> str | None:
    """One Gemini call. Every failure returns None - nothing escapes to the caller."""
    if genai is None or not GEMINI_API_KEY:
        log.warning("mentor: no Gemini (%s) - staying quiet",
                    "package missing" if genai is None else "GEMINI_API not set in .env")
        return None
    log.debug("mentor: prompt = %s", prompt)
    try:
        resp = await _gemini().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=persona,
                max_output_tokens=GEMINI_MAX_TOKENS,
                temperature=GEMINI_TEMPERATURE,
                thinking_config=_thinking(),
        # We run the tool loop ourselves in _converse(), so the SDK's automatic path must be
        # off. Leaving it on is what prints the "Direct use of automatic function calling"
        # warning on every single call, even ones that declare no tools at all.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except errors.ClientError as exc:
        # 4xx: bad key, malformed request, quota exhausted. Retrying will not help - it is ours.
        log.warning("mentor: gemini rejected the request (%s)", exc)
        return None
    except errors.ServerError as exc:
        # 5xx: Google's side. The next trigger tries again, so there is nothing to do here.
        log.warning("mentor: gemini unavailable (%s)", exc)
        return None
    except Exception as exc:
        log.warning("mentor: gemini call failed (%s: %s)", type(exc).__name__, exc)
        return None

    # resp.text is None when the reply was blocked or produced no candidates - not an error,
    # but not something to speak either.
    text = (resp.text or "").strip()
    if not text:
        reason = getattr(resp.candidates[0], "finish_reason", None) if resp.candidates else None
        log.warning("mentor: gemini returned no text (finish_reason=%s)", reason)
        return None
    return _for_speech(text)


def _thinking():
    """Keep deliberation cheap - a one-line nudge needs none.

    Returns None when GEMINI_THINKING is blank or names a level this SDK does not know, which
    leaves the model on its own default rather than failing the call.
    """
    level = getattr(types.ThinkingLevel, GEMINI_THINKING, None) if GEMINI_THINKING else None
    return types.ThinkingConfig(thinking_level=level) if level else None


def _gemini():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _for_speech(text: str) -> str:
    """Last line of defence on length.

    The token cap usually holds, but a model that talks past it would have the speaker going for
    twenty seconds. Keep the first two sentences, and drop a trailing fragment from a cut-off.
    """
    text = " ".join(text.split())          # collapse newlines; they read badly aloud
    sentences, buf = [], ""
    for ch in text:
        buf += ch
        if ch in ".!?":
            sentences.append(buf.strip())
            buf = ""
            if len(sentences) == 2:
                break
    return " ".join(sentences) if sentences else buf.strip()



def build_prompt(trigger: Trigger, context: dict) -> str:
    """Turn the context dict into the text Gemini sees.

    Separate from compose() on purpose: you will iterate on this wording far more often than on
    the API call, and it is the one piece worth being able to print and read on its own.

    TODO: write the real prompt.
    """

    SYSTEM_PROMPT = """
                        You are Mentor Buddy, a personal AI productivity mentor whose sole purpose is to keep the user focused, productive, and moving toward their goals. Analyze the full context provided—including recent activity, productivity patterns, the current task, and the user's goal for today if one exists—and respond based on what the user actually needs right now. If trigger.level = 1, the user is still generally productive but appears to be drifting, so gently redirect them with a concise, motivating message and a little playful sarcasm when appropriate; do not treat this as a failure. If trigger.level = 2, the user has clearly drifted from productive behavior, so become a firm, direct, and motivating mentor who tells them to stop the distraction and return to meaningful work, using their goal as the anchor when available. If no goal is provided, encourage them toward the most productive direction evident from their context without inventing a goal. Always be context-aware, concise, restrictive when necessary, and action-oriented; never shame, insult, threaten, over-explain, or give generic motivational speeches. Speak naturally as a mentor who knows what the user is working toward. Return only the message intended for the user, preferably 1–2 sentences and no more than 40 words.
                    """
    return (
        f"[{SYSTEM_PROMPT}]\n"
        f"tone: {tone(trigger.level)}\n"
        f"why now: {context['trigger_reason']}\n"
        f"productivity score: {context['score_now']:.2f}\n"
        f"last {context['hours']:.0f}h: {context['totals']}\n"
        f"where the time went: {context['places']}\n"
        f"still to do today: {context['goals_open']}\n"
        f"already finished: {context['goals_done']}\n"
    )


def tone(level: int) -> str:
    """Soft and hard should not sound the same."""
    return {SOFT: "gentle, curious, one question",
            HARD: "direct, concrete, name what they are doing"}.get(level, "neutral")


async def speak(nudge: Nudge) -> None:
    """Render the line and leave it for the ESP32 to collect.

    Failing here is not fatal - the nudge still happened, it just was not heard. voice.say()
    swallows its own errors and returns None, so nothing propagates back to the MATLAB worker.
    """
    clip = await voice.say(nudge.text)
    if clip is None:
        log.warning("mentor: could not render audio, nudge went unheard")


# --- wiring --------------------------------------------------------------------------------

def make_handler(pool: asyncpg.Pool):
    """Bind the pool so matlab.py stays unaware of the database."""
    async def handler(trigger: Trigger) -> None:
        await handle(trigger, pool)
    return handler


def state() -> dict:
    """What /health reports."""
    return {"last_nudge": None if _last is None else
            {"text": _last.text, "level": _last.level, "at": _last.at.isoformat()}}
