from __future__ import annotations

import logging
from datetime import date

import asyncpg

from engine.config import DATABASE_URL, LOCAL_TZ

log = logging.getLogger("uvicorn.error")

SCHEMA = """
-- Columns added after the table already existed somewhere. `create table if not exists` does
-- nothing to a table that is already there, so new columns need saying explicitly. Postgres
-- makes these no-ops on a database that already has them.
alter table if exists user_profile add column if not exists lat double precision;
alter table if exists user_profile add column if not exists lng double precision;
alter table if exists user_profile add column if not exists location_accuracy_m double precision;
alter table if exists user_profile add column if not exists location_at timestamptz;

-- Every time Buddy speaks on its own. Without this a nudge exists only in memory and is gone
-- on restart: the dashboard cannot show what happened today, and a demo cannot be replayed.
-- Writes are bounded by the cooldown (at most one per MATLAB_HARD_COOLDOWN_S), so this is one
-- small insert every 20+ seconds at worst, on a path that is already waiting on Gemini.
create table if not exists nudge (
    id         bigserial primary key,
    at         timestamptz not null default now(),
    level      int         not null,          -- 1 soft, 2 hard
    reason     text,                          -- MATLAB's own words
    score      double precision,              -- the running score when it fired
    text       text        not null,          -- what Buddy actually said
    spoken     boolean     not null default false,  -- did audio get rendered for the watch
    -- what the user was doing at that moment, copied so the row stands alone
    domain     text,
    title      text,
    duration_s double precision
);
create index if not exists nudge_at_idx on nudge (at desc);

-- Who Buddy is talking to. One row, because Buddy runs on one person's machine - the fixed
-- primary key makes that structural rather than a convention. The onboarding `goal` is the
-- standing ambition ("graduate with a 3.8"), which is a different thing from the daily rows in
-- `goals`; Gemini is given both, and it greets the user by name from here.
create table if not exists user_profile (
    id           text primary key,          -- always 'local'
    name         text,
    email        text,
    university   text,
    major        text,
    level        text,                      -- freshman / senior / grad ...
    study_hours  text,                      -- how much they intend to study
    peak_time    text,                      -- when they focus best
    distraction  text,                      -- what usually derails them
    needs        text[],                    -- what they want help with
    goal         text,                      -- the standing goal
    -- Where the laptop last reported itself. Sent by the dashboard from the browser's
    -- geolocation, which on macOS is Wi-Fi triangulation - roughly ten metres, and far better
    -- than anything the engine can work out on its own.
    lat          double precision,
    lng          double precision,
    location_accuracy_m double precision,
    location_at  timestamptz,
    onboarded_at timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- What was said out loud, both directions. Append-only: Buddy should remember a conversation
-- across an engine restart, so this cannot live in process memory. Only the plain spoken turns
-- are kept - never the prompt Gemini is built with, and never the tool traffic.
create table if not exists conversation (
    id         bigserial primary key,
    role       text        not null,   -- 'user' or 'model', the roles Gemini expects back
    text       text        not null,
    created_at timestamptz not null default now()
);
create index if not exists conversation_recent_idx on conversation (id desc);

-- What the user means to do today. One row per goal per day, so "read 30 pages" on Monday and
-- the same goal on Tuesday are separate rows with their own outcomes.
create table if not exists goals (
    id           bigserial primary key,
    goal_date    date        not null default current_date,
    title        text        not null,          

    -- What counts toward it. Both optional: a goal can be a plain reminder with no measurement.
    target_minutes int,                         
    match_terms    text[],                      

    priority   int  not null default 0,         -- higher sorts first in the UI
    source     text not null default 'user',    -- 'user' or 'buddy' if Gemini proposed it
    carried_from date,                          -- set when rolled over from an unfinished day
    created_at timestamptz not null default now(),

    -- The same goal must not be added twice in one day.
    unique (goal_date, title)
);
create index if not exists goals_date_idx on goals (goal_date desc);

-- Goals that were actually finished. A separate table on purpose: this is an event log,
create table if not exists completed_goals (
    id            bigserial primary key,
    goal_id       bigint      references goals (id) on delete cascade,
    goal_date     date        not null default current_date,
    title         text        not null,         -- copied, so history survives a deleted goal
    completed_at  timestamptz not null default now(),

    actual_minutes  double precision,           -- measured from activity, not self-reported
    score_at_finish double precision,           -- the running score when it was ticked off
    note            text,                       -- "took longer than expected"

    -- Ticking the same goal twice is a no-op, not a second row.
    unique (goal_id)
);
create index if not exists completed_goals_date_idx on completed_goals (goal_date desc);

create table if not exists activity (
    -- which session, and when
    session_id    text        not null,
    start_ts      timestamptz not null,
    end_ts        timestamptz not null,
    duration_s    double precision not null,   -- also the high-water mark of counted time
    tz_offset_min int,
    device_id     text,

    -- what you were doing
    app_name   text,
    app_type   text,
    domain     text,
    title      text,
    model_text text,                           -- exactly what TF-IDF saw

    -- the verdict
    p     double precision not null,
    label text not null,
    model text,

    -- your running score right after this session last updated
    score_after double precision,

    -- housekeeping
    is_final   boolean not null default false,
    end_reason text,
    updated_at timestamptz not null default now(),

    primary key (session_id, start_ts)
);
create index if not exists activity_end_ts_idx on activity (end_ts desc);
create index if not exists activity_updated_idx on activity (updated_at desc);
"""

COLUMNS = ("session_id", "start_ts", "end_ts", "duration_s", "tz_offset_min", "device_id",
           "app_name", "app_type", "domain", "title", "model_text", "p", "label", "model",
           "score_after", "is_final", "end_reason")

UPSERT = f"""
insert into activity ({", ".join(COLUMNS)})
values ({", ".join(f"${i}" for i in range(1, len(COLUMNS) + 1))})
on conflict (session_id, start_ts) do update set
    -- duration never goes backwards: rows can arrive out of order, and a late early heartbeat
    -- must not shrink a session that has already grown past it.
    end_ts      = greatest(excluded.end_ts, activity.end_ts),
    duration_s  = greatest(excluded.duration_s, activity.duration_s),
    title       = coalesce(nullif(excluded.title, ''), activity.title),
    model_text  = excluded.model_text,
    p           = excluded.p,
    label       = excluded.label,
    model       = excluded.model,
    score_after = excluded.score_after,
    is_final    = excluded.is_final,
    end_reason  = excluded.end_reason,
    updated_at  = now()
returning duration_s
"""


def dsn() -> str:
    if not DATABASE_URL:
        raise RuntimeError("TIMESCALE_SERVICE_URL is not set - check .env")
    return DATABASE_URL


async def connect() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(dsn(), min_size=1, max_size=5, command_timeout=15)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)
    log.info("db: connected, schema ready")
    return pool


async def load_state(pool: asyncpg.Pool) -> tuple[float | None, dict[str, tuple[float, bool]]]:
    """The score to resume from, and how long each recent session has already been counted for.

    The map is a cache of the duration column so the common path is a single round trip; the
    upsert's greatest() still protects the stored value if the cache is ever stale.
    """
    async with pool.acquire() as conn:
        score = await conn.fetchval(
            "select score_after from activity where score_after is not null "
            "order by updated_at desc limit 1")
        rows = await conn.fetch("select session_id, duration_s, is_final from activity "
                                "where end_ts > now() - interval '1 day'")
    return score, {r["session_id"]: (r["duration_s"], r["is_final"]) for r in rows}


async def upsert_activity(pool: asyncpg.Pool, record: dict) -> float:
    async with pool.acquire() as conn:
        return await conn.fetchval(UPSERT, *(record[c] for c in COLUMNS))


async def recent_scores(pool: asyncpg.Pool, limit: int) -> list[tuple[float, float]]:
    """The last `limit` (epoch_seconds, score) points, oldest first.

    This is what the MATLAB window is primed from on startup. Without it the engine has to
    re-earn 20 live sessions after every restart before it can ask MATLAB anything, which in
    practice means a whole working day of silence.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select end_ts, score_after from activity where score_after is not null "
            "order by end_ts desc limit $1", limit)
    return [(r["end_ts"].timestamp(), float(r["score_after"])) for r in reversed(rows)]


# --- goals -------------------------------------------------------------------------------
# The point of match_terms: a goal is measured against the activity table rather than trusted.
# "2 hours on the thesis" with match_terms {overleaf.com, Preview} knows how it is going without
# the user reporting anything, and Gemini can say "you are 40 minutes short" instead of guessing.

GOALS_TODAY = """
select g.*,
       c.completed_at,
       c.actual_minutes,
       coalesce((
           select sum(a.duration_s) / 60.0
           from activity a
           -- The local day, not the UTC one. start_ts is timestamptz; AT TIME ZONE converts
           -- it to wall-clock time in the user's zone, so "today" ends at their midnight.
           where (a.start_ts at time zone $2)::date = g.goal_date
             and g.match_terms is not null
             and (a.domain = any (g.match_terms) or a.app_name = any (g.match_terms))
       ), 0) as minutes_spent
from goals g
left join completed_goals c on c.goal_id = g.id
where g.goal_date = $1
order by g.priority desc, g.id
"""


async def goals_for(pool: asyncpg.Pool, day=None) -> list[dict]:
    """Today's goals, each with how far along it is and whether it was finished."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(GOALS_TODAY, day or date.today(), LOCAL_TZ)
    return [dict(r) for r in rows]


async def add_goal(pool: asyncpg.Pool, title: str, target_minutes: int | None = None,
                   match_terms: list[str] | None = None, priority: int = 0,
                   source: str = "user", day=None) -> dict:
    """Add a goal. Adding the same title twice in a day updates it instead of duplicating."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            insert into goals (goal_date, title, target_minutes, match_terms, priority, source)
            values ($1, $2, $3, $4, $5, $6)
            on conflict (goal_date, title) do update set
                target_minutes = excluded.target_minutes,
                match_terms    = excluded.match_terms,
                priority       = excluded.priority
            returning *""",
            day or date.today(), title, target_minutes, match_terms, priority, source)
    return dict(row)


async def complete_goal(pool: asyncpg.Pool, goal_id: int, score: float | None = None,
                        note: str | None = None) -> dict | None:
    """Tick a goal off, recording the minutes actually spent on it.

    The minutes come from the activity table, not from the user - that is the whole reason
    match_terms exists. Ticking an already-completed goal is a no-op.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            insert into completed_goals (goal_id, goal_date, title, actual_minutes,
                                         score_at_finish, note)
            select g.id, g.goal_date, g.title,
                   -- coalesce: sum() over no matching activity is NULL, and "0 minutes" is the
                   -- honest answer there, not "unknown". Matches what goals_for() reports.
                   coalesce((select sum(a.duration_s) / 60.0 from activity a
                    where (a.start_ts at time zone $4)::date = g.goal_date
                      and g.match_terms is not null
                      and (a.domain = any (g.match_terms) or a.app_name = any (g.match_terms))),
                            0),
                   $2, $3
            from goals g where g.id = $1
            on conflict (goal_id) do nothing
            returning *""", goal_id, score, note, LOCAL_TZ)
    return dict(row) if row else None


async def completed_on(pool: asyncpg.Pool, day=None) -> list[dict]:
    """What was finished on a given day - what Gemini reads to give credit."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from completed_goals where goal_date = $1 order by completed_at",
            day or date.today())
    return [dict(r) for r in rows]


# --- what Buddy said, unprompted -----------------------------------------------------------

async def record_nudge(pool: asyncpg.Pool, *, level: int, reason: str, score: float,
                       text: str, spoken: bool, activity: dict | None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            insert into nudge (level, reason, score, text, spoken, domain, title, duration_s)
            values ($1, $2, $3, $4, $5, $6, $7, $8) returning id""",
            level, reason, score, text, spoken,
            (activity or {}).get("domain"), (activity or {}).get("title"),
            (activity or {}).get("duration_s"))


async def nudges_between(pool: asyncpg.Pool, start, end) -> list[dict]:
    """Everything Buddy said in a window, oldest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from nudge where at >= $1 and at < $2 order by at", start, end)
    return [dict(r) for r in rows]


# --- who the user is ----------------------------------------------------------------------

PROFILE_FIELDS = ("name", "email", "university", "major", "level",
                  "study_hours", "peak_time", "distraction", "needs", "goal")


async def get_profile(pool: asyncpg.Pool) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select * from user_profile where id = 'local'")
    return dict(row) if row else None


async def save_location(pool: asyncpg.Pool, lat: float, lng: float,
                        accuracy_m: float | None) -> None:
    """Record where the laptop says it is. Kept on the profile so it survives a restart."""
    async with pool.acquire() as conn:
        await conn.execute("""
            insert into user_profile (id, lat, lng, location_accuracy_m, location_at)
            values ('local', $1, $2, $3, now())
            on conflict (id) do update set
                lat = $1, lng = $2, location_accuracy_m = $3,
                location_at = now(), updated_at = now()""", lat, lng, accuracy_m)


async def save_profile(pool: asyncpg.Pool, data: dict) -> dict:
    """Upsert the single profile row. Re-running onboarding updates rather than duplicates."""
    values = [data.get(f) for f in PROFILE_FIELDS]
    sets = ", ".join(f"{f} = ${i + 2}" for i, f in enumerate(PROFILE_FIELDS))
    cols = ", ".join(PROFILE_FIELDS)
    holes = ", ".join(f"${i + 2}" for i in range(len(PROFILE_FIELDS)))
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"insert into user_profile (id, {cols}) values ($1, {holes}) "
            f"on conflict (id) do update set {sets}, updated_at = now() returning *",
            "local", *values)
    return dict(row)


# --- conversation ------------------------------------------------------------------------

async def recent_conversation(pool: asyncpg.Pool, limit: int) -> list[tuple[str, str]]:
    """The last `limit` spoken turns, oldest first - the order Gemini wants them in."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select role, text from conversation order by id desc limit $1", limit)
    return [(r["role"], r["text"]) for r in reversed(rows)]


async def append_conversation(pool: asyncpg.Pool, turns: list[tuple[str, str]]) -> None:
    """Record one exchange. Both turns go in together so a crash cannot split a pair."""
    async with pool.acquire() as conn:
        await conn.executemany(
            "insert into conversation (role, text) values ($1, $2)", turns)


async def delete_goal(pool: asyncpg.Pool, goal_id: int) -> bool:
    """Remove a goal. Its completion row, if any, cascades away with it."""
    async with pool.acquire() as conn:
        result = await conn.execute("delete from goals where id = $1", goal_id)
    return result.split()[-1] != "0"


async def uncomplete_goal(pool: asyncpg.Pool, goal_id: int) -> bool:
    """Untick a goal - ticking the wrong row should not be permanent."""
    async with pool.acquire() as conn:
        result = await conn.execute("delete from completed_goals where goal_id = $1", goal_id)
    return result.split()[-1] != "0"


async def carry_over(pool: asyncpg.Pool, to_day=None) -> int:
    """Roll yesterday's unfinished goals into today, remembering where they came from."""
    target = to_day or date.today()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            insert into goals (goal_date, title, target_minutes, match_terms, priority,
                               source, carried_from)
            select $1, g.title, g.target_minutes, g.match_terms, g.priority,
                   g.source, g.goal_date
            from goals g
            left join completed_goals c on c.goal_id = g.id
            where g.goal_date = $1 - 1 and c.goal_id is null
            on conflict (goal_date, title) do nothing""", target)
    return int(result.split()[-1])


# --- what the dashboard reads ------------------------------------------------------------
# All of these are local-day aware: a productivity dashboard's "today" ends at the user's
# midnight, not at 7pm when the UTC date rolls over.

async def latest_activity(pool: asyncpg.Pool) -> dict | None:
    """The most recently updated session - what the user is doing right now."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select * from activity order by updated_at desc limit 1")
    return dict(row) if row else None


async def score_series(pool: asyncpg.Pool, since, until=None) -> list[dict]:
    """Every stored score point in a window, oldest first - the productivity line."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select end_ts, score_after from activity "
            "where score_after is not null and end_ts >= $1 "
            "  and ($2::timestamptz is null or end_ts <= $2) "
            "order by end_ts", since, until)
    return [{"ts": r["end_ts"], "score": float(r["score_after"])} for r in rows]


async def day_stats(pool: asyncpg.Pool, start, end) -> dict:
    """Totals for one local day, plus the hour the user was most productive.

    `slumps` counts the number of times the score CROSSED below 0.5, not the number of rows
    below it - sitting at 0.3 for an hour is one incident, not two hundred.
    """
    async with pool.acquire() as conn:
        totals = await conn.fetchrow("""
            select coalesce(sum(duration_s), 0)                            as tracked_s,
                   coalesce(sum(duration_s * p) / nullif(sum(duration_s), 0), 0) as avg_p,
                   count(*)                                                as sessions
            from activity where end_ts >= $1 and end_ts < $2""", start, end)
        slumps = await conn.fetchval("""
            with ordered as (
                select score_after,
                       lag(score_after) over (order by end_ts) as prev
                from activity where end_ts >= $1 and end_ts < $2 and score_after is not null)
            select count(*) from ordered
            where score_after < 0.5 and (prev is null or prev >= 0.5)""", start, end)
        best = await conn.fetchrow("""
            select date_trunc('hour', end_ts at time zone $3) as hour,
                   sum(duration_s * p) / nullif(sum(duration_s), 0) as score
            from activity where end_ts >= $1 and end_ts < $2
            group by 1 having sum(duration_s) > 60
            order by score desc nulls last limit 1""", start, end, LOCAL_TZ)
    return {"tracked_s": float(totals["tracked_s"]), "avg_p": float(totals["avg_p"]),
            "sessions": totals["sessions"], "slumps": slumps or 0,
            "best_hour": best["hour"] if best else None}


async def activity_since(pool: asyncpg.Pool, since, limit: int = 500) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from activity where end_ts >= $1 order by start_ts limit $2", since, limit)
    return [dict(r) for r in rows]


async def summary(pool: asyncpg.Pool, since) -> dict:
    """The window boiled down small enough to put in a prompt."""
    async with pool.acquire() as conn:
        totals = await conn.fetchrow("""
            select coalesce(sum(duration_s), 0) as tracked,
                   coalesce(sum(duration_s * p), 0) as productive,
                   count(*) as sessions
            from activity where end_ts >= $1""", since)
        places = await conn.fetch("""
            select coalesce(domain, app_name, 'unknown') as name,
                   sum(duration_s) as seconds,
                   sum(duration_s * p) / nullif(sum(duration_s), 0) as p
            from activity where end_ts >= $1
            group by 1 order by seconds desc limit 10""", since)
    return {"totals": dict(totals), "places": [dict(p) for p in places]}


async def current_score(pool: asyncpg.Pool) -> float | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "select score_after from activity where score_after is not null "
            "order by updated_at desc limit 1")
