"""

    matlab.Trigger  ->  gather_context()  ->  compose()  ->  speak()
                        (read the db)        (Gemini)        (ElevenLabs -> ESP32)

"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from engine import db, maps, voice
from engine.config import (GEMINI_API_KEY, GEMINI_MAX_TOKENS, GEMINI_MODEL,
                           GEMINI_TEMPERATURE, GEMINI_THINKING, LOCAL_TZ)
from engine.matlab import Trigger
from engine.store_helpers import now

try:
    from google import genai
    from google.genai import errors, types
except ImportError:      # the engine still runs without it; Buddy just stays quiet
    genai = None

log = logging.getLogger("uvicorn.error")

# Who Buddy is. Sent as a system instruction rather than glued onto the prompt, so the facts in
# build_prompt() stay separate from the character - you can iterate on either alone.
# The nudge persona. This is the user's own wording, moved here verbatim from inside
# build_prompt() where it was being sent as USER content while a second, competing persona
# went in as the system instruction - so Gemini received two sets of rules that disagreed
# on length and on tone, and the system one silently won. One persona, in the slot that
# actually outranks the rest of the prompt.
NUDGE_PERSONA = (
    "You are Mentor Buddy, a personal AI productivity mentor whose sole purpose is to keep the "
    "user focused, productive, and moving toward their goals. Analyze the full context "
    "provided—including recent activity, productivity patterns, the current task, and the user's "
    "goal for today if one exists—and respond based on what the user actually needs right now. If "
    "trigger.level = 1, the user is still generally productive but appears to be drifting, so "
    "gently redirect them with a concise, motivating message and a little playful sarcasm and a sassy nature like that of tony stark, iron man, when "
    "appropriate; do not treat this as a failure. If trigger.level = 2, the user has clearly "
    "drifted from productive behavior, so become a firm, direct, and motivating mentor who tells "
    "them to stop the distraction and return to meaningful work, using their goal as the anchor "
    "when available. If no goal is provided, encourage them toward the most productive direction "
    "evident from their context without inventing a goal. Always be context-aware, concise, "
    "restrictive when necessary, and action-oriented; never shame, insult, threaten, "
    "over-explain, or give generic motivational speeches. Speak naturally as a mentor who wants "
    "the user to be productive and stop wasting time. Return only the message intended for the "
    "user, preferably 1–2 sentences and no more than 40 words."
)

# The watch button is a conversation, not an interruption - so it gets a little more room and
# is allowed to answer a question rather than only redirect.
ANSWER_PERSONA = """You are Buddy. You are this person's productivity mentor - not an
assistant, not a chatbot, not a search engine. You know them by name, you know what they are
trying to build, you know how they have spent their day because you have been watching it, and
you can see where they are. Everything you say serves one purpose: getting them to the thing
they said mattered to them.

Who you are talking to: a young adult who is capable and ambitious, and who loses hours to
distraction without noticing. They did not ask for a cheerleader. They asked for someone who
will keep them honest.

WHAT YOU CAN DO
You have tools. Use them instead of guessing - you have real data, so there is never a reason
to estimate.
- Goals: propose one when they name something they want to get done, tick one off when they say
  they finished it, remove one when they ask. Proposing and removing are read back and
  confirmed out loud before anything is written. Ticking off is not.
- Travel: you can find out how long it takes them to get somewhere from where they are right
  now, on foot, by bike, by car or on transit.

WHEN A GOAL HAS A PLACE OR A TIME IN IT
This is where you earn your keep. If they say they need to be somewhere by a certain time, work
out the answer before you reply:
  1. Check how long it takes to get there.
  2. Compare it against the current time, which you are given.
  3. Tell them the departure time, not the travel time. "You need to leave by 2:47" is useful.
     "It is a thirteen minute walk" makes them do the arithmetic themselves.
Then set the goal if that is what they wanted. Do not ask their permission to check the
distance - just check it.

If a tool tells you it does not know where they are, or cannot find the place, say exactly that
and what would fix it. Never invent a distance, a duration or a departure time.

HOW YOU SPEAK
- Two or three short sentences. This is read aloud through a small speaker. Long is useless.
- Plain spoken. No corporate warmth, no "I'm here to help you", no offering your services.
  You are already in their life; you do not introduce yourself like a product.
- Use their first name. Say "you", not "the user".
- Concrete over general. "Forty minutes on YouTube" beats "some distraction". A time beats a
  duration. A named goal beats "your work".

HOW YOU BEHAVE
- Answer the question they actually asked. Then stop. Do not append a lecture.
- You are not a general-purpose assistant. If they ask you trivia, or to write something, or
  anything unrelated to their work and their focus, give the shortest honest answer you can and
  turn it back to what they are supposed to be doing. One clause, not a speech.
- When they are drifting, name it plainly and say what to do next. Do not soften it into
  nothing. Do not ask permission to be direct.
- When they are doing well, say so once, briefly, and get out of the way.
- Never shame them, never guilt them, never moralise, never threaten. Directness is not cruelty.
  You are on their side, and it should be obvious that you are.
- Never invent facts about their day, their location, or their time. If you were not given it
  and no tool will tell you, you do not know it.

No greetings as an opener, no sign-offs, no emoji, no markdown, no bullet points. Just say the
thing, the way a person who respects them would say it."""

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

    spoken = await speak(nudge)
    _last = nudge

    # Record it AFTER speaking, so `spoken` is the truth rather than an intention. This runs on
    # the MATLAB worker, well off the ingest path, and the cooldown means at most one write per
    # 20 seconds - next to the Gemini and ElevenLabs calls above it, the insert is noise.
    try:
        await db.record_nudge(pool, level=nudge.level, reason=nudge.reason, score=nudge.score,
                              text=nudge.text, spoken=spoken,
                              activity=await db.latest_activity(pool))
    except Exception as exc:
        # Losing the record costs the dashboard a row, not the user their nudge.
        log.warning("mentor: could not record the nudge (%s: %s)", type(exc).__name__, exc)
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
    profile = await db.get_profile(pool) or {}
    return {
        "name": profile.get("name") or "",
        "standing_goal": profile.get("goal") or "",
        "trigger_level": trigger.level,          # 1 soft, 2 hard
        "trigger_reason": trigger.reason,        # e.g. "above 0.5 but dropping 3 consecutive"
        "score_now": trigger.score,
        "hours": CONTEXT_HOURS,
        # Durations go in as SPOKEN text, never as bare numbers. Handing the model
        # {'tracked': 90.8} with no unit had it read seconds as minutes: 45 seconds on YouTube
        # came back as "forty-five minutes", 75 seconds as "over an hour". The model was not
        # hallucinating, it was guessing a unit we never gave it.
        "totals": _totals(good_summary["totals"]),
        "places": _places(good_summary["places"]),
        # What they meant to do today. This is what lets a nudge be specific - "you are 40
        # minutes short on the wiring" rather than a generic "get back to work".
        "goals_open": [_goal_brief(g) for g in todays_goals if not g["completed_at"]],
        "goals_done": [g["title"] for g in todays_goals if g["completed_at"]],
    }


def say_duration(seconds) -> str:
    """A duration the way a person would say it out loud, with the unit attached."""
    secs = float(seconds or 0)
    if secs < 90:
        return f"{round(secs)} seconds"
    if secs < 90 * 60:
        return f"{secs / 60:.0f} minutes"
    return f"{secs / 3600:.1f} hours"


def _totals(totals: dict) -> str:
    return (f"{say_duration(totals['tracked'])} tracked, of which "
            f"{say_duration(totals['productive'])} productive, across "
            f"{totals['sessions']} sessions")


def _places(places: list) -> str:
    if not places:
        return "nothing tracked"
    parts = []
    for place in places:
        line = f"{place['name']} {say_duration(place['seconds'])}"
        if place["p"] is not None:
            line += f" (productivity {float(place['p']):.2f})"
        parts.append(line)
    return "; ".join(parts)


def _goal_brief(goal: dict) -> dict:
    """Just enough of a goal for a prompt: what it is, and how far off it is."""
    return {"title": goal["title"],
            "target_minutes": goal["target_minutes"],
            "minutes_spent": round(float(goal["minutes_spent"]), 1),
            "carried_from": goal["carried_from"].isoformat() if goal["carried_from"] else None}


async def compose(trigger: Trigger, context: dict) -> str | None:
    return await _generate(build_prompt(trigger, context), NUDGE_PERSONA)


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
            name="complete_goal",
            description=(
                "Tick a goal off as finished, when the user says they have done it. The title "
                "does not have to match exactly - say roughly what they said and it will be "
                "matched against today's list. Safe to call directly; it can be undone."),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"title": types.Schema(
                    type=types.Type.STRING,
                    description="Which goal they finished, in their words.")},
                required=["title"])),
        types.FunctionDeclaration(
            name="propose_removal",
            description=(
                "Call this when the user wants a goal taken off the list entirely - not "
                "finished, removed. Like propose_goal, this does NOT delete anything: read the "
                "goal back and ask them to confirm first, because deletion is permanent."),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"title": types.Schema(
                    type=types.Type.STRING,
                    description="Which goal to remove, in their words.")},
                required=["title"])),
        types.FunctionDeclaration(
            name="travel_time",
            description=(
                "How long it takes to get somewhere from where the user is right now. Use it "
                "whenever a place, a distance or 'how long to get to...' comes up, and use it "
                "before agreeing to a goal that requires being somewhere at a time. If it "
                "reports it does not know where they are, say so plainly instead of guessing."),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "destination": types.Schema(
                        type=types.Type.STRING,
                        description="Where they are going, as a place name or address."),
                    "mode": types.Schema(
                        type=types.Type.STRING,
                        description="walk, drive, bike or transit. Default walk."),
                },
                required=["destination"])),
        types.FunctionDeclaration(
            name="confirm_goal",
            description=(
                "Carry out whatever you last proposed - saving a new goal, or removing one. "
                "Call this ONLY after the user has clearly agreed out loud. Never call it in "
                "the same turn as propose_goal or propose_removal."),
            parameters=types.Schema(type=types.Type.OBJECT, properties={})),
        types.FunctionDeclaration(
            name="cancel_goal",
            description="Drop what you proposed, when the user declines or changes their mind.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})),
    ])]


async def _find_goal(pool, spoken: str) -> dict | None:
    """Match what the user said against today's goals.

    Speech-to-text will not reproduce a title word for word, so an exact match is useless here.
    Exact first, then a containment match either way round, so "the math one" finds "finish my
    math assignment".
    """
    goals = await db.goals_for(pool)
    said = (spoken or "").strip().lower()
    if not said:
        return None
    for goal in goals:
        if goal["title"].strip().lower() == said:
            return goal
    hits = [g for g in goals if said in g["title"].lower() or g["title"].lower() in said]
    return hits[0] if len(hits) == 1 else None


async def _call_tool(name: str, args: dict, pool) -> dict:
    """Run one tool. The return value goes back to Gemini as the function response."""
    global _pending_goal

    if name == "propose_goal":
        # Conversation history keeps only the spoken turns, not the tool traffic, so the model
        # has no memory that it already proposed something. Re-proposing over a live proposal
        # left it looping - ask, get a yes, ask again. Refuse and point at confirm_goal.
        if _pending_goal is not None:
            return {"status": "already_pending", "action": _pending_goal["action"],
                    "title": _pending_goal["title"],
                    "next": "You already proposed this and are waiting on them. If they just "
                            "agreed, call confirm_goal. If they changed it, call cancel_goal "
                            "first."}
        _pending_goal = {"action": "add", "title": args["title"],
                         "target_minutes": args.get("target_minutes"),
                         "match_terms": args.get("match_terms")}
        log.info("mentor: goal proposed (awaiting confirmation) %r", _pending_goal["title"])
        return {"status": "awaiting_confirmation", **_pending_goal,
                "next": "Read the goal back and ask the user to confirm. Do not save it yet."}

    if name == "propose_removal":
        goal = await _find_goal(pool, args.get("title", ""))
        if goal is None:
            return {"status": "not_found", "goals": [g["title"] for g in await db.goals_for(pool)],
                    "next": "Say you could not find that one and read back what is on the list."}
        _pending_goal = {"action": "remove", "id": goal["id"], "title": goal["title"]}
        log.info("mentor: removal proposed (awaiting confirmation) %r", goal["title"])
        return {"status": "awaiting_confirmation", "action": "remove", "title": goal["title"],
                "next": "Deleting is permanent. Name the goal and ask them to confirm."}

    if name == "confirm_goal":
        if not _pending_goal:
            return {"status": "nothing_to_confirm",
                    "next": "Ask what they would like to do."}
        pending, _pending_goal = _pending_goal, None

        if pending["action"] == "remove":
            gone = await db.delete_goal(pool, pending["id"])
            log.warning("mentor: goal removed -> %r", pending["title"])
            return {"status": "removed" if gone else "not_found", "title": pending["title"]}

        saved = await db.add_goal(pool, title=pending["title"],
                                  target_minutes=pending["target_minutes"],
                                  match_terms=pending["match_terms"],
                                  source="buddy")
        log.warning("mentor: goal saved -> %r (id %s)", saved["title"], saved["id"])
        return {"status": "saved", "id": saved["id"], "title": saved["title"]}

    if name == "cancel_goal":
        _pending_goal = None
        return {"status": "cancelled"}

    if name == "travel_time":
        result = await maps.travel(pool, args["destination"], args.get("mode", "walk"))
        if result["ok"]:
            log.info("maps: %s -> %s min, %s km (%s)", result["destination"],
                     result["minutes"], result["km"], result["mode"])
        else:
            log.info("maps: %s (%s)", result["reason"], result.get("detail", "")[:80])
        # Every other tool reports a "status"; matching that keeps the tool log readable.
        return {**result, "status": "ok" if result["ok"] else result["reason"]}

    if name == "complete_goal":
        goal = await _find_goal(pool, args.get("title", ""))
        if goal is None:
            return {"status": "not_found", "goals": [g["title"] for g in await db.goals_for(pool)],
                    "next": "Say which goals are open and ask which one they finished."}
        # No confirmation step: finishing something is not destructive, and it can be undone.
        done = await db.complete_goal(pool, goal["id"], score=None)
        if done is None:
            return {"status": "already_done", "title": goal["title"]}
        log.warning("mentor: goal completed -> %r (%s minutes measured)",
                    done["title"], round(float(done["actual_minutes"] or 0), 1))
        return {"status": "completed", "title": done["title"],
                "minutes_measured": round(float(done["actual_minutes"] or 0), 1),
                "next": "Acknowledge it briefly. Do not make a speech about it."}

    return {"status": "unknown_tool"}


async def answer(question: str, pool) -> str | None:
    """Reply to something the user said into the watch microphone.

    Same model and voice, different job: this one is a conversation, so it may reference the
    goals and the day rather than nudging about them.
    """
    summary = await db.summary(pool, now() - timedelta(hours=CONTEXT_HOURS))
    goals = await db.goals_for(pool)
    profile = await db.get_profile(pool) or {}

    # The question comes FIRST and alone, with the data explicitly demoted to reference.
    # Listing the question as one line among five lines of browsing stats had the model treating
    # the stats as the topic - ask it the time and it would start talking about YouTube.
    # Durations are spoken text here for the same reason they are in build_prompt(): given a
    # bare 90.8 with no unit, the model reads seconds as minutes.
    who = profile.get("name")
    prompt = (
        f'The user said, out loud: "{question}"\n\n'
        f"Answer that, and only that. Everything below is background you may draw on IF it is "
        f"relevant to what they actually asked. Do not bring up their browsing, their score or "
        f"their goals unless the question is about them.\n\n"
        f"--- background ---\n"
        # Without this it cannot turn "class at 3" into "leave in twelve minutes" - it would
        # have to guess the time, and it guesses badly.
        f"right now it is: {datetime.now(ZoneInfo(LOCAL_TZ)):%A %d %B, %H:%M} "
        f"({LOCAL_TZ})\n"
        f"who you are talking to: {who or 'unknown'}\n"
        + (f"awaiting their yes or no: {_pending_goal['action']} "
           f"\"{_pending_goal['title']}\" - if they agree, confirm it; do not propose it "
           f"again\n" if _pending_goal else "")
        + (
        f"their standing goal: {profile.get('goal') or 'not set'}\n"
        f"productivity score right now: {await _score_hint(pool)}\n"
        f"last {CONTEXT_HOURS:.0f}h: {_totals(summary['totals'])}\n"
        f"where the time went: {_places(summary['places'])}\n"
        f"still to do today: {[_goal_brief(g) for g in goals if not g['completed_at']]}\n"
        f"already finished: {[g['title'] for g in goals if g['completed_at']]}\n"
        )
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
    """The facts for one nudge. No persona here - that is NUDGE_PERSONA, sent as the system
    instruction, which outranks anything written into the user turn.

    `trigger.level` is named explicitly because the persona branches on it by that name.
    """
    return (
        f"trigger.level = {trigger.level}\n"
        f"why now: {context['trigger_reason']}\n"
        f"right now it is: {datetime.now(ZoneInfo(LOCAL_TZ)):%A %d %B, %H:%M}\n"
        f"you are talking to: {context['name'] or 'unknown'}\n"
        f"their standing goal: {context['standing_goal'] or 'not set'}\n"
        f"productivity score: {context['score_now']:.2f}\n"
        f"last {context['hours']:.0f}h: {context['totals']}\n"
        f"where the time went: {context['places']}\n"
        f"still to do today: {context['goals_open']}\n"
        f"already finished: {context['goals_done']}\n"
    )


async def speak(nudge: Nudge) -> bool:
    """Render the line and leave it for the ESP32 to collect. True if audio was produced.

    Failing here is not fatal - the nudge still happened, it just was not heard. voice.say()
    swallows its own errors and returns None, so nothing propagates back to the MATLAB worker.
    """
    clip = await voice.say(nudge.text)
    if clip is None:
        log.warning("mentor: could not render audio, nudge went unheard")
    return clip is not None


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
