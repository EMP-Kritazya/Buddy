# backend/ — FastAPI Brain

**Owner:** Kritazya (P2)  
**Keys:** GEMINI_API_KEY, TIGER_DSN — in NordPass

## What lives here

| File | Purpose |
|---|---|
| `main.py` | FastAPI app — all endpoints, Gemini, Tiger Data, SQLite fallback, speech queue |
| `requirements.txt` | pip dependencies |
| `fallback.db` | Auto-created SQLite DB when Tiger Cloud is unavailable |

## Endpoints

| Method | Path | Called by | Does |
|---|---|---|---|
| POST | `/voice` | Watch (P1) | WAV in → Scribe STT → Gemini JSON → tasks stored → TTS WAV out |
| POST | `/events` | PC agent (P4) | Insert event row; auto-classifies if score not provided |
| GET | `/events` | Dashboard (P3) | Raw event feed, newest first |
| GET | `/stats` | Dashboard (P3) | Time-bucketed avg score for chart |
| GET | `/timeline` | Dashboard (P3) | Alias for `/events` |
| GET | `/tasks` | All | Today's open tasks |
| GET | `/journal` | Dashboard (P3) | Markdown journal for the day |
| POST | `/coach` | PC agent (P4) | Gemini coaching line → TTS → enqueue on `/pending-speech` |
| GET | `/pending-speech` | Watch (P1) | Watch polls every 2 s; 204 = nothing waiting |

## Gemini JSON mode (every `/voice` call)

```
System: You are Buddy. Return JSON:
{
  "reply": "spoken text ≤20 s",
  "tasks_add": [{title, deadline, priority, estimate_min}],
  "tasks_update": [{id, status}]
}
Suggest shortest task first. No medical advice.
```

## Start the server

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Set env vars first (see `../.env.example`):

```bash
export GEMINI_API_KEY=...
export ELEVENLABS_API_KEY=...
export TIGER_DSN=postgresql://...   # leave blank to use SQLite fallback
```

## Tiger Data schema

Run once against the Tiger Cloud instance:

```sql
CREATE TABLE tasks (...);
CREATE TABLE events (...);
SELECT create_hypertable('events','ts');
CREATE TABLE incidents (...);
SELECT create_hypertable('incidents','ts');
```

Full DDL in `../shared/schema.md`.

## Tonight exit

- [ ] `uvicorn main:app` starts with no errors
- [ ] `POST /events` with `{"app":"League of Legends","window_title":"League of Legends"}` → `{"score":12,"label":"unproductive"}`
- [ ] `POST /voice` with a typed text body (if STT is late) → Gemini adds two tasks, returns reply text
- [ ] `GET /tasks` returns those tasks
