# Buddy — Backend Integration Guide
> For the FastAPI + Tiger Data backend engineer.
> This document tells you exactly what the frontend expects.
> Every endpoint, every data shape, every field name.

---

## Stack Overview

```
Frontend:  React + TypeScript + Vite (Lovable)
Backend:   FastAPI (Python)
Database:  Tiger Data (TimescaleDB / PostgreSQL)
AI:        Gemini API
TTS/STT:   ElevenLabs
Hardware:  LilyGO T-Display-S3 (ESP32-S3) via Wi-Fi
```

---

## How to Connect

### Step 1 — Set CORS in FastAPI
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Lovable dev
        "https://your-lovable-url.lovable.app",
        "https://your-production-url.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Step 2 — Tell Sandesh to update .env
```env
VITE_USE_REAL_API=true
VITE_API_URL=http://your-server-ip:8000
```

### Step 3 — Everything switches automatically
No frontend code changes needed.
One env variable flips all 16 endpoints
from preview data to real API.

---

## Authentication

All endpoints (except /auth/*) require:
```
Authorization: Bearer <token>
Content-Type: application/json
```

---

## Score Format — CRITICAL

```
Scores are ALWAYS sent as 0 to 1 (float)
NOT 0 to 100.

Frontend multiplies × 100 for display.
0.84 → displays as "84"
0.5  → displays as "50" (neutral threshold)

Trigger values:
0 = OK, productive (score >= 0.5, no drops)
1 = SOFT, sliding down (3 consecutive drops, still >= 0.5)
2 = HARD, unproductive (score < 0.5, always wins)

Timestamps: ISO 8601 format
"2026-09-12T21:14:00Z"
```

---

## Trigger Logic (from MATLAB)

```
TRIGGER 0 — OK:
  current score >= 0.5
  AND no 3 consecutive distinct drops

TRIGGER 1 — SOFT:
  current score >= 0.5
  AND last 3 distinct values strictly decreasing

TRIGGER 2 — HARD:
  current score < 0.5
  (always wins regardless of slope)
```

---

## All 22 Endpoints

### AUTH

#### POST /api/auth/signup
```json
Request:
{
  "email": "sandesh@uta.edu",
  "password": "password123"
}

Response:
{
  "token": "jwt_token_here",
  "userId": "uuid"
}
```

#### POST /api/auth/login
```json
Request:
{
  "email": "sandesh@uta.edu",
  "password": "password123"
}

Response:
{
  "token": "jwt_token_here",
  "userId": "uuid"
}
```

---

### USERS

#### POST /api/users/onboarding
> Called once after signup. Seeds Gemini with user context.
```json
Request:
{
  "name": "Sandesh",
  "email": "sandesh@uta.edu",
  "university": "University of Texas at Arlington",
  "major": "Computer Science",
  "level": "Sophomore",
  "studyHours": "5-6 hrs",
  "peakTime": "Afternoon",
  "distraction": "Gaming",
  "needs": [
    "Staying focused during study sessions",
    "Reducing distractions"
  ],
  "goal": "Finish senior design and maintain 3.9 GPA"
}

Response:
{
  "success": true,
  "userId": "uuid"
}
```

#### GET /api/users/profile
```json
Response:
{
  "name": "Sandesh",
  "email": "sandesh@uta.edu",
  "university": "University of Texas at Arlington",
  "major": "Computer Science",
  "level": "Sophomore",
  "peakTime": "Afternoon",
  "goal": "Finish senior design and maintain 3.9 GPA"
}
```

#### PATCH /api/users/profile
```json
Request (any subset of fields):
{
  "name": "Sandesh",
  "university": "UTA",
  "goal": "Updated goal"
}

Response:
{
  "success": true
}
```

---

### SCORES
> These are the most critical endpoints.
> PC agent sends data here every 30 seconds.

#### GET /api/scores/current
> Used by: Home dashboard left panel, Live page top stats
> Poll interval: every 30 seconds
```json
Response:
{
  "timestamp": "2026-09-12T21:35:00Z",
  "score": 0.84,
  "trigger": 0,
  "app_name": "Visual Studio Code",
  "window_title": "Senior Design Dashboard",
  "session_duration": 42
}
```

#### GET /api/scores/live
> Used by: Live page chart (rolling 30 min window)
> Poll interval: every 30 seconds
```json
Response:
[
  {
    "timestamp": "2026-09-12T21:05:00Z",
    "score": 0.76,
    "trigger": 0,
    "app_name": "Visual Studio Code"
  },
  {
    "timestamp": "2026-09-12T21:10:00Z",
    "score": 0.80,
    "trigger": 0,
    "app_name": "Visual Studio Code"
  },
  {
    "timestamp": "2026-09-12T21:14:00Z",
    "score": 0.12,
    "trigger": 2,
    "app_name": "League of Legends"
  }
]
```

#### GET /api/scores/today
> Used by: Discover page full day chart
> Poll interval: every 5 minutes
```json
Response:
[
  {
    "timestamp": "2026-09-12T08:00:00Z",
    "score": 0.62,
    "trigger": 0,
    "app_name": "Chrome"
  },
  {
    "timestamp": "2026-09-12T10:00:00Z",
    "score": 0.81,
    "trigger": 0,
    "app_name": "Visual Studio Code"
  }
]
```

#### POST /api/scores (PC Agent sends here)
> PC agent posts every 30 seconds
```json
Request:
{
  "timestamp": "2026-09-12T21:35:00Z",
  "score": 0.84,
  "trigger": 0,
  "app_name": "Visual Studio Code",
  "window_title": "Senior Design Dashboard"
}

Response:
{
  "success": true
}
```

---

### TASKS

#### GET /api/tasks/current
> Used by: Home left panel "current task", right panel "next priority"
> Poll interval: every 60 seconds
```json
Response:
{
  "id": "task_uuid",
  "title": "Senior design until 10 PM",
  "due_time": "22:00",
  "status": "in_progress",
  "priority": "high",
  "minutes_left": 28,
  "source": "user"
}
```

#### GET /api/tasks/today
> Used by: Home right panel task list
> Poll interval: every 60 seconds
```json
Response:
[
  {
    "id": "1",
    "title": "Email professor",
    "due_time": "18:00",
    "status": "missed",
    "priority": "high",
    "source": "user"
  },
  {
    "id": "2",
    "title": "Senior design until 10 PM",
    "due_time": "22:00",
    "status": "in_progress",
    "priority": "high",
    "source": "user"
  },
  {
    "id": "3",
    "title": "Review slides",
    "due_time": "21:00",
    "status": "todo",
    "priority": "medium",
    "source": "user"
  }
]
```

#### GET /api/tasks/tomorrow
> Used by: Home tomorrow section
```json
Response:
[
  {
    "id": "t1",
    "title": "Email professor first thing",
    "priority": "high"
  },
  {
    "id": "t2",
    "title": "Start thesis outline",
    "priority": "medium"
  }
]
```

#### POST /api/tasks
> Called when user adds a task manually
```json
Request:
{
  "title": "Review slides",
  "due_time": "21:00",
  "priority": "medium",
  "source": "user"
}

Response:
{
  "id": "new_uuid",
  "title": "Review slides",
  "due_time": "21:00",
  "status": "todo",
  "priority": "medium",
  "source": "user"
}
```

#### POST /api/tasks/tomorrow
> Called when user adds tomorrow task
```json
Request:
{
  "title": "Email professor first thing",
  "priority": "high"
}

Response:
{
  "id": "new_uuid",
  "title": "Email professor first thing",
  "priority": "high"
}
```

#### PATCH /api/tasks/:id
> Called when user marks task done/progress/todo
```json
Request:
{
  "status": "done"
}

Response:
{
  "success": true
}
```

---

### INCIDENTS

#### GET /api/incidents/today
> Used by: Home incident count, Discover incidents list
> Poll interval: every 60 seconds
```json
Response:
[
  {
    "id": "inc_1",
    "timestamp": "2026-09-12T21:14:00Z",
    "app_name": "League of Legends",
    "duration_secs": 54,
    "score": 0.12,
    "trigger": 2,
    "intervened": true,
    "gemini_response": "You've been on League for 4 minutes. Want to come back?"
  }
]
```

---

### WEARABLE

#### GET /api/wearable/status
> Used by: Home left panel wearable dot
> Poll interval: every 10 seconds
```json
Response:
{
  "connected": true,
  "last_trigger_time": "21:14",
  "last_trigger_message": "Stay on track.",
  "trigger_type": "hard"
}
```

#### GET /api/wearable/messages
> Used by: Live page "What Buddy said today"
> Poll interval: every 60 seconds
```json
Response:
[
  {
    "time": "21:14",
    "message": "You've been away for 4 minutes. Want to come back?",
    "type": "hard"
  },
  {
    "time": "19:30",
    "message": "You've been focused for 2 hours. Take a short break.",
    "type": "soft"
  },
  {
    "time": "17:15",
    "message": "Senior design deadline is in 3 hours. On track?",
    "type": "soft"
  }
]
```

---

### GEMINI / AI

#### GET /api/gemini/commentary
> Used by: Live page right column commentary
> Poll interval: every 30 seconds
> Gemini generates these based on score changes
```json
Response:
[
  {
    "id": "c1",
    "time": "21:35",
    "text": "You've been focused for 42 minutes. Strong work.",
    "type": "positive"
  },
  {
    "id": "c2",
    "time": "21:14",
    "text": "League detected. Score hit 12. You recovered fast.",
    "type": "incident"
  },
  {
    "id": "c3",
    "time": "20:45",
    "text": "Productivity dipping. Check what's open.",
    "type": "warning"
  }
]

Types: "positive" | "warning" | "incident"
```

#### GET /api/gemini/day-analysis
> Used by: Discover page right column
> Poll interval: every 5 minutes
```json
Response:
[
  {
    "id": "d1",
    "time": "21:14",
    "period": null,
    "text": "League of Legends for 54 seconds. Score hit 12. Buddy intervened.",
    "type": "incident"
  },
  {
    "id": "d2",
    "time": null,
    "period": "18:00 – 21:00",
    "text": "Strongest 3-hour block. Avg score 86. VS Code the entire time.",
    "type": "positive"
  },
  {
    "id": "d3",
    "time": null,
    "period": "14:00 – 16:00",
    "text": "Deep focus period. Productivity peaked at 91.",
    "type": "positive"
  }
]
```

#### GET /api/gemini/suggestions
> Used by: Home right panel "from your wearable"
> Poll interval: every 5 minutes
```json
Response:
[
  {
    "id": "s1",
    "text": "Break your senior design into three parts before 10 PM.",
    "updated_at": "2026-09-12T21:31:00Z"
  },
  {
    "id": "s2",
    "text": "Start with the hardest part first.",
    "updated_at": "2026-09-12T21:17:00Z"
  },
  {
    "id": "s3",
    "text": "Close YouTube before 9 PM.",
    "updated_at": "2026-09-12T20:46:00Z"
  }
]
```

---

### SUMMARY

#### GET /api/summary/today
> Used by: Discover page stats + tomorrow suggestion
> Poll interval: every 5 minutes
```json
Response:
{
  "focus_time_mins": 262,
  "avg_score": 0.84,
  "incident_count": 1,
  "tasks_completed": 1,
  "tasks_total": 3,
  "strongest_period": "2:00 PM – 6:00 PM",
  "gemini_reflection": "Your strongest work was between 2PM and 6PM. One interruption at 9:14 pulled your score down, but you recovered in under 2 minutes.",
  "tomorrow_suggestion": "Email your professor before opening anything else tomorrow."
}
```

---

### JOURNAL

#### GET /api/journal/today
> Used by: Journal page
```json
Response:
{
  "date": "2026-09-12",
  "markdown": "# Buddy Journal — 12 Sep 2026\n\n## Goals\n- Email professor\n- Senior design until 10 PM\n\n## Incidents\n- 21:14 — League of Legends (score 0.12, 54s)\n\n## Suggestion\nEmail first tomorrow before opening anything else.",
  "goals": [
    "Email professor",
    "Senior design until 10 PM"
  ],
  "incidents": [
    "21:14 — League of Legends (score 0.12, 54s)"
  ],
  "suggestion": "Email your professor before opening anything else tomorrow."
}
```

#### GET /api/journal/history
> Used by: Journal history list
```json
Response:
[
  {
    "date": "2026-09-12",
    "preview": "Strong afternoon focus. One interruption at 9:14 PM.",
    "avg_score": 0.84,
    "focus_time_mins": 262
  },
  {
    "date": "2026-09-11",
    "preview": "Solid morning session. Deadline met.",
    "avg_score": 0.79,
    "focus_time_mins": 198
  }
]
```

---

## Tiger Data Schema

```sql
-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Users table
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Onboarding / profile
CREATE TABLE user_profiles (
  user_id       UUID REFERENCES users(id),
  name          TEXT,
  university    TEXT,
  major         TEXT,
  level         TEXT,
  study_hours   TEXT,
  peak_time     TEXT,
  distraction   TEXT,
  needs         TEXT[],
  goal          TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Productivity scores (hypertable — time series)
CREATE TABLE productivity_scores (
  user_id       UUID REFERENCES users(id),
  timestamp     TIMESTAMPTZ NOT NULL,
  score         FLOAT NOT NULL,      -- 0 to 1
  trigger       SMALLINT NOT NULL,   -- 0, 1, or 2
  app_name      TEXT,
  window_title  TEXT
);

SELECT create_hypertable(
  'productivity_scores', 
  'timestamp'
);

-- Tasks
CREATE TABLE tasks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id),
  date          DATE NOT NULL,
  title         TEXT NOT NULL,
  due_time      TEXT,
  status        TEXT DEFAULT 'todo',
  priority      TEXT DEFAULT 'medium',
  source        TEXT DEFAULT 'user',  -- 'user' or 'gemini'
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Incidents
CREATE TABLE incidents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id),
  timestamp     TIMESTAMPTZ NOT NULL,
  app_name      TEXT,
  duration_secs INT,
  score         FLOAT,
  trigger       SMALLINT,
  intervened    BOOLEAN DEFAULT FALSE,
  gemini_response TEXT
);

-- Wearable messages
CREATE TABLE wearable_messages (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id),
  timestamp     TIMESTAMPTZ NOT NULL,
  message       TEXT,
  trigger_type  TEXT   -- 'soft' or 'hard'
);

-- Daily summaries (computed end of day)
CREATE TABLE daily_summaries (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID REFERENCES users(id),
  date                DATE NOT NULL,
  focus_time_mins     INT,
  avg_score           FLOAT,
  incident_count      INT,
  tasks_completed     INT,
  tasks_total         INT,
  strongest_period    TEXT,
  gemini_reflection   TEXT,
  tomorrow_suggestion TEXT,
  journal_markdown    TEXT
);
```

---

## Polling Schedule (frontend polls these)

```
Every 10 seconds:
  GET /api/wearable/status

Every 30 seconds:
  GET /api/scores/current
  GET /api/scores/live
  GET /api/gemini/commentary

Every 60 seconds:
  GET /api/tasks/current
  GET /api/tasks/today
  GET /api/incidents/today
  GET /api/wearable/messages
  GET /api/gemini/suggestions

Every 5 minutes:
  GET /api/scores/today
  GET /api/summary/today
  GET /api/gemini/day-analysis

On demand (user action):
  GET /api/journal/today
  GET /api/journal/history
  GET /api/tasks/tomorrow
  POST /api/tasks/tomorrow
  PATCH /api/tasks/:id
```

---

## Gemini Personalization

When /api/users/onboarding is called,
seed Gemini with this system prompt:

```
You are Buddy, a personal productivity 
companion for [name].

User context:
- Studies [major] at [university]
- Current level: [level]
- Studies [studyHours] per day
- Most productive in the [peakTime]
- Biggest distraction: [distraction]
- Needs help with: [needs]
- Main goal this semester: [goal]

Use this context to:
1. Generate personalized coaching messages
2. Write daily journal reflections
3. Suggest tasks that align with their goal
4. Comment on their productivity patterns

Always be warm, direct, and human.
Never say "productivity anomaly" or 
"behavior violation". 
Sound like a wise friend, not software.
```

---

## Priority Build Order

```
Build these first (dashboard needs them):
1. POST /api/auth/signup
2. POST /api/auth/login
3. POST /api/users/onboarding
4. GET  /api/scores/current
5. GET  /api/scores/live
6. POST /api/scores (PC agent posts here)

Then these (complete the dashboard):
7.  GET /api/tasks/today
8.  GET /api/tasks/current
9.  GET /api/incidents/today
10. GET /api/wearable/status
11. GET /api/gemini/suggestions

Then these (Discover + Journal):
12. GET /api/scores/today
13. GET /api/summary/today
14. GET /api/gemini/commentary
15. GET /api/gemini/day-analysis
16. GET /api/journal/today

Finally:
17. GET /api/journal/history
18. GET /api/tasks/tomorrow
19. POST /api/tasks/tomorrow
20. PATCH /api/tasks/:id
21. GET /api/users/profile
22. PATCH /api/users/profile
```

---

## How to Test Each Endpoint

Once an endpoint is ready, tell Sandesh:

```
"Endpoint X is ready at http://ip:8000"
```

Sandesh updates .env:
```
VITE_USE_REAL_API=true
VITE_API_URL=http://ip:8000
```

Frontend automatically uses real data.
No code changes needed on frontend.

---

*Built at HackRice 16 · September 2026*
*Buddy — Your attention has a story.*
