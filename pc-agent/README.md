# pc-agent/ — Windows Window Logger + Coaching Trigger

**Owner:** Suyog (P1 / P4 overlap)  
**Platform:** Windows only (uses `ctypes.windll`)

## What lives here

| File | Purpose |
|---|---|
| `agent.py` | Foreground app poller → classify → POST /events → CSV → slump trigger |
| `triggers.json` | Tunable thresholds — edit live, no restart needed |

## What it does every second

```
app, title = foreground window
idle_s     = seconds since last key/mouse
if changed or 5s elapsed:
    classify(app, title, idle_s, open_tasks)  → score 0–100
    POST /events
    append buddy_score.csv
    if rolling_avg < score_threshold for streak_seconds:
        POST /coach  {tasks, now, app, score, streak_s, last_productive_app}
```

## Trigger settings (`triggers.json`)

| Key | Default | Meaning |
|---|---|---|
| `score_threshold` | 35 | Rolling avg score that counts as a slump |
| `streak_seconds` | 45 | How long the slump must last before coaching fires |
| `cooldown_seconds` | 180 | Minimum gap between two coaching events |
| `require_open_deadline_task` | true | Only coach when at least one open task has a deadline |

Edit this file while `agent.py` is running — it reloads triggers on each poll cycle.

## CSV format (`../buddy_score.csv`)

```
timestamp,score,app
2026-09-12T21:14:03+00:00,12,League of Legends
```

MATLAB and Lovable both read from this file.

## How to run

```bash
cd pc-agent
pip install requests
python agent.py
```

Set `BUDDY_API` env var if the backend is not on `127.0.0.1:8000`:

```bash
set BUDDY_API=http://192.168.1.100:8000
python agent.py
```

## Tonight exit

- [ ] Console prints foreground app name on every change
- [ ] `buddy_score.csv` grows with real rows
- [ ] After alt-tabbing to a game for 45 s: `[coach] fired →` line appears in console
- [ ] `POST /coach` reaches the backend and returns a coaching sentence
