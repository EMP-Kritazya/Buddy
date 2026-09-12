# Buddy — shared contracts (freeze tonight)

## Event row  (PC → Tiger Data via POST /events)

```json
{
  "ts": "2026-09-12T21:14:03-05:00",
  "source": "pc",
  "app": "League of Legends",
  "window_title": "League of Legends",
  "category": "gaming",
  "label": "unproductive",
  "score": 12,
  "confidence": 0.93,
  "duration_s": 8,
  "idle_s": 0,
  "active_task_id": "task_senior_design"
}
```

`score` 0–100. `label`: productive | unproductive | mixed | idle | break.

## Task object

```json
{
  "id": "task_senior_design",
  "title": "Senior design",
  "deadline": "2026-09-12T22:00:00-05:00",
  "priority": 2,
  "status": "open",
  "estimate_min": null
}
```

## Coach request (pc-agent → POST /coach)

```json
{
  "tasks": ["today's task list as strings"],
  "now": "21:14",
  "current_app": "League of Legends",
  "score": 12,
  "unproductive_streak_s": 54,
  "last_productive_app": "VS Code"
}
```

Gemini returns short spoken text only (≤20 s). No medical advice. One task reminder + one next action.

## Endpoints

| Method | Path | Owner | Purpose |
|---|---|---|---|
| POST | /voice | P2 | audio in → STT → Gemini → TTS → audio out |
| POST | /events | P2 | insert event row from PC agent |
| GET | /events | P2 | raw event feed |
| GET | /stats | P2 | time-bucketed score averages |
| GET | /timeline | P2 | score + app timeline |
| GET | /tasks | P2 | today's tasks |
| GET | /journal | P2 | markdown journal for the day |
| POST | /coach | P2 | trigger Gemini coaching line → enqueue audio |
| GET | /pending-speech | P2 | watch polls for unsolicited audio |
