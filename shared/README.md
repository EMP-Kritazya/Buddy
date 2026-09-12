# shared/ — Contracts (freeze tonight)

**Owner:** All four — read by everyone, changed by agreement only  
**Freeze:** Tonight before 2 AM. No unilateral changes after that.

## What lives here

| File | Purpose |
|---|---|
| `schema.md` | Event row, task object, coach request shapes + endpoint table |

## Why this exists

Four people posting to the same API need to agree on field names once. If you change a field name here after freeze, you break at least one other person's code.

## Change process (during the hackathon)

1. Announce the change in the group chat
2. Edit `schema.md`
3. Update **both** sides (producer + consumer) in the same commit
4. Tell everyone to pull

## Key contracts

### Event row (PC → `/events`)
`ts, source, app, window_title, category, label, score(0–100), confidence, duration_s, idle_s, active_task_id`

### Task object (stored by backend, read by all)
`id, title, deadline(ISO or null), priority(int), status(open|done), estimate_min`

### Coach request (pc-agent → `/coach`)
`tasks(list[str]), now(HH:MM), current_app, score, unproductive_streak_s, last_productive_app`

### Coach response (Gemini → backend → watch)
Plain spoken text, ≤ 20 seconds when read aloud. No JSON. No medical advice.

## Full detail

See [`schema.md`](schema.md).
