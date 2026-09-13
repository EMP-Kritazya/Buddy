# Mentor Buddy

An AI productivity mentor that watches what you are actually doing, decides when you have
drifted, and says something about it out loud.

Most focus tools block a website. But `youtube.com` is where you watch a linear algebra lecture
_and_ where you watch sketch comedy — a blocklist cannot tell those apart, so you disable it.
Buddy classifies the **content** instead. Its model learned that the word `lecture` (+3.18)
outweighs the domain `youtube` (−2.70), so on the same site it leaves you alone for one and
speaks up for the other.

---

## How it works

```
  Chrome extension          FastAPI engine (localhost)              Devices
 ┌────────────────┐        ┌──────────────────────────────┐       ┌─────────────┐
 │ focus sessions │───────▶│ clean → TF-IDF → LogReg → p  │       │   ESP32-S3  │
 │ heartbeat 30s  │ POST   │              ↓               │       │  watch      │
 └────────────────┘/ingest │   EMA score 0–1, time-weighted│      └──────┬──────┘
                           │              ↓               │  GET /pending-speech
                           │      TigerData (Postgres)    │◀─────────────┘
                           │              ↓               │       polls every 2s
                           │   MATLAB ── trigger 0/1/2 ──▶│
                           │              ↓               │       ┌─────────────┐
                           │   Gemini + 7 tools ──────────┼──────▶│  dashboard  │
                           │              ↓               │  /api │  (React)    │
                           │   ElevenLabs → audio mailbox │       └─────────────┘
                           └──────────────────────────────┘
```

1. **Capture** — a Chrome extension turns browsing into _focus sessions_, not clicks. A
   heartbeat every 30s means a long video reports while it is still playing.
2. **Classify** — each session becomes one string (`domain` + `title`), vectorised with TF-IDF
   and scored by logistic regression into `p`, a probability of being productive.
3. **Score** — `p` moves a running 0–1 score, weighted by time spent: a 30-second glance barely
   moves it, twenty minutes moves it most of the way.
4. **Decide** — the score series streams to MATLAB, which reads the _trend_ and returns a
   trigger level: 0 fine, 1 drifting, 2 distracted.
5. **Speak** — Gemini writes the line, ElevenLabs voices it, and the ESP32 watch collects and
   plays it.

**It never sees your screen.** No screenshots, no keystrokes, no page content — only the domain
and the tab title. Incognito windows, `chrome://` pages, extensions and local files are never
logged.

---

## Tech stack

<p align="center">
  <img src="https://img.shields.io/badge/Python_3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white" />
  <img src="https://img.shields.io/badge/TimescaleDB-FDB515?style=for-the-badge&logo=postgresql&logoColor=black" />
  <img src="https://img.shields.io/badge/MATLAB-0076A8?style=for-the-badge&logo=mathworks&logoColor=white" />
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white" />
  <img src="https://img.shields.io/badge/ElevenLabs-000000?style=for-the-badge&logo=elevenlabs&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Maps-4285F4?style=for-the-badge&logo=googlemaps&logoColor=white" />
  <img src="https://img.shields.io/badge/ESP32--S3-E7352C?style=for-the-badge&logo=espressif&logoColor=white" />
</p>
<p align="center">
  <img src="https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TanStack-FF4154?style=for-the-badge&logo=reactquery&logoColor=white" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" />
  <img src="https://img.shields.io/badge/Tailwind-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" />
  <img src="https://img.shields.io/badge/Chrome_MV3-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" />
</p>

```mermaid
flowchart TB
    subgraph SENSE["🔍 SENSE"]
        direction LR
        EXT["Chrome MV3<br/><i>vanilla JS</i>"]
        MIC["I2S mic<br/><i>ESP32-S3</i>"]
    end

    subgraph THINK["🧠 THINK"]
        direction LR
        API["FastAPI + uvicorn<br/><i>async, one process</i>"]
        ML["scikit-learn<br/><i>TF-IDF + LogReg</i>"]
        MAT["MATLAB<br/><i>trend → trigger</i>"]
    end

    subgraph REMEMBER["💾 REMEMBER"]
        DB[("TigerData<br/><i>Postgres 18 · 7 tables</i>")]
    end

    subgraph SPEAK["🗣️ SPEAK"]
        direction LR
        GEM["Gemini<br/><i>7 tools, agentic</i>"]
        MAP["Google Routes<br/><i>travel time</i>"]
        EL["ElevenLabs<br/><i>TTS + Scribe STT</i>"]
        AMP["I2S amp<br/><i>ESP32-S3</i>"]
    end

    subgraph SEE["📊 SEE"]
        UI["React 19 · TanStack<br/>Vite · Tailwind · Recharts"]
    end

    EXT -->|"POST /ingest"| API
    MIC -->|"POST /voice"| API
    API --> ML --> DB
    DB --> MAT --> GEM
    GEM <--> MAP
    GEM --> EL --> AMP
    DB --> UI
    GEM -.->|"reads + writes"| DB

    classDef sense fill:#1e3a5f,stroke:#4a90d9,color:#fff
    classDef think fill:#2d1b4e,stroke:#9b6dd7,color:#fff
    classDef store fill:#4a3800,stroke:#fdb515,color:#fff
    classDef speak fill:#4a1520,stroke:#e0475f,color:#fff
    classDef see fill:#0d3b3b,stroke:#2dd4bf,color:#fff

    class EXT,MIC sense
    class API,ML,MAT think
    class DB store
    class GEM,MAP,EL,AMP speak
    class UI see
```

<details>
<summary><b>Why each piece</b></summary>

| Layer    | Choice                        | Reason                                                                                |
| -------- | ----------------------------- | ------------------------------------------------------------------------------------- |
| Capture  | Chrome Extension, Manifest V3 | Service worker can die at any moment, so all state lives in `chrome.storage`          |
| Engine   | FastAPI + asyncpg             | One local process; every I/O path awaits rather than blocking                         |
| ML       | TF-IDF + LogisticRegression   | ~1 ms to score, so it can sit on the request path — and the coefficients are readable |
| Storage  | TigerData (TimescaleDB)       | Managed Postgres. Plain tables, not hypertables — the row count never justified them  |
| Trend    | MATLAB Production Server      | Reads the _trend_, not a threshold, so it catches drift before the hour is gone       |
| LLM      | Gemini with function calling  | Tool declarations keep the persona untouched; writes need confirmation                |
| Voice    | ElevenLabs, PCM 16 kHz mono   | No MP3 decoder on the ESP32 — raw samples go straight to the I2S buffer               |
| Device   | ESP32-S3, 320 KB RAM          | Streams in 2 KB chunks; it can never hold a whole clip                                |
| Frontend | TanStack Start + Recharts     | SSR-capable, and the chart samples the live score every 2 s                           |

</details>

## Setup

### Prerequisites

- **Python 3.13+** and **Node 20+**
- A **Postgres** database — [TigerData](https://www.tigerdata.com/) free tier works
- API keys: **Gemini**, **ElevenLabs**, and optionally **Google Maps**
- Optional: an ESP32-S3 board, and MATLAB Production Server

### 1. Engine

```bash
git clone <your-repo> Buddy && cd Buddy

python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt

cp .env.example .env      # then fill it in — see below
```

> **Always use `venv/bin/python`, never a bare `python3`.** The model is a pickle of
> scikit-learn's own objects and can only be loaded by the version that wrote it. A different
> interpreter silently falls back to the keyword rules in `ml/rules.py` and the ML does nothing.

Fill in `.env`:

```ini
TIMESCALE_SERVICE_URL=postgres://user:pass@host:port/db?sslmode=require
GEMINI_API=...          # ai.google.dev
ELEVEN_API=...          # elevenlabs.io
MAPS_API=...            # optional — enable the Routes API on the project
MATLAB_URL=...          # optional
MATLAB_TOKEN=...        # optional
```

Start it:

```bash
venv/bin/python -m uvicorn engine.app:app --host 0.0.0.0 --port 8000
```

Tables are created on first connect. A healthy start looks like:

```
scorer: loaded tfidf-logreg-...        ← the ML model, not the fallback rules
db: connected, schema ready
engine: watch should use  SERVER = "http://192.168.x.x:8000"
reminders: worker started
matlab: worker started
```

> `--host 0.0.0.0` is required if you have the ESP32. Uvicorn binds `127.0.0.1` by default,
> which only this machine can reach.

Check it: `curl -s localhost:8000/health | python3 -m json.tool`

### 2. Chrome extension

1. `chrome://extensions` → enable **Developer mode**
2. **Load unpacked** → select the `extension/` folder
3. Browse. Sessions appear in the engine's terminal within ~30 seconds.

Click the Buddy toolbar icon to see the queue depth and last sync.

### 3. Dashboard

```bash
cd ../frontend
npm install
npm run dev          # http://localhost:8080
```

`.env` there needs:

```ini
VITE_API_URL=http://localhost:8000
VITE_USE_REAL_API=true
```

> Vite reads `.env` **only at startup**. Change it and you must restart the dev server — a
> hot reload will not pick it up.

Open the dashboard once and allow location access if you want travel-time answers.

### 4. Canned audio (before any demo)

```bash
curl -X POST http://localhost:8000/audio/generate
```

Renders four fallback clips into `audio/`. These are the only thing that still speaks when
ElevenLabs or Gemini is unavailable, and the watch caches them to its own flash on first boot.

### 5. ESP32 watch (optional)

Edit `firmware/buddy_watch/buddy_watch.ino`:

```c
const char* WIFI_SSID = "your-wifi";
const char* WIFI_PASS = "your-password";
const char* SERVER    = "http://192.168.x.x:8000";   // printed at engine startup
```

Requires Arduino-ESP32 core, `TFT_eSPI` with the T-Display-S3 setup, and a 16 MB flash
partition scheme with FATFS. Test without hardware:

```bash
curl -X POST "http://localhost:8000/speak/test?text=Buddy%20is%20connected"
```

---

## Training the model

A trained `ml/model.joblib` is committed, so this is optional.

```bash
venv/bin/python -m ml.generate --n 1000   # synthesise labelled sessions
venv/bin/python -m ml.extract             # pull real sessions out of data/sessions.jsonl
venv/bin/python -m ml.train               # train, evaluate, save ml/model.joblib
curl -X POST http://localhost:8000/model/reload   # pick it up without a restart
```

`train.py` reports two splits. Trust the **by-template** one — a random split leaks near
duplicates between train and test and flatters the result.

```
random_80_20       accuracy 0.987   recall 0.991
by_template_80_20  accuracy 0.925   recall 1.000   ← the honest number
```

Recall on the productive class is deliberately favoured: interrupting someone who is genuinely
working is the expensive mistake.

---

## API

**Sensors**
| | |
|---|---|
| `POST /ingest` | sessions from the extension |
| `GET /pending-speech` | the watch polls this every 2s — 204 or a WAV |
| `POST /voice` | push-to-talk: raw PCM in, spoken answer out |
| `GET /audio/{name}` | canned clips the watch caches |

**Dashboard** — `/api/scores/{current,live,today}`, `/api/summary/today`,
`/api/tasks/*`, `/api/incidents/today`, `/api/wearable/*`, `/api/users/{profile,onboarding,location}`

**Operations**
| | |
|---|---|
| `GET /health` | model, database, MATLAB and voice status |
| `POST /mentor/test?level=2` | fire a nudge by hand |
| `POST /matlab/check` | verify the MATLAB tunnel |
| `POST /model/reload` | reload the classifier |

Interactive docs at `http://localhost:8000/docs`.

---

## Layout

```
Buddy/
├── engine/            FastAPI engine
│   ├── app.py         startup, routers, background workers
│   ├── ingest.py      sensor front door
│   ├── pipeline.py    clean → classify → score → store
│   ├── scoring.py     the model, with a rules fallback
│   ├── score.py       the running 0–1 EMA
│   ├── db.py          the ONLY Postgres-aware file
│   ├── matlab.py      trend triggers
│   ├── mentor.py      Gemini, personas, the 7 tools
│   ├── voice.py       ElevenLabs + the watch's mailbox
│   ├── maps.py        travel time
│   ├── reminders.py   fires reminders on time
│   └── web.py         /api/* for the dashboard
├── ml/                generate, extract, train, prep, rules
├── extension/         Chrome MV3 capture
├── firmware/          ESP32-S3 sketch
├── audio/             fallback clips
└── data/              sessions.jsonl, the local audit trail
```

Seven tables: `activity`, `goals`, `completed_goals`, `nudge`, `conversation`,
`user_profile`, `reminder`.

---

## Troubleshooting

**`scorer: ... using rules`** — wrong interpreter. Use `venv/bin/python`.

**The watch cannot reach the engine** — start with `--host 0.0.0.0`, and check the laptop and
device are on the same network. Guest networks usually block device-to-device traffic
entirely; a phone hotspot is the fastest fix.

**Dashboard shows nothing** — open devtools. `apiClient` logs every failed call by name. Most
often the engine is not running, or the Vite dev server predates the `.env` change.

**`429 RESOURCE_EXHAUSTED` from Gemini** — the free tier allows 20 requests per day _per
model_. Switch `GEMINI_MODEL` in `.env` for a fresh allowance, or enable billing.

**`Routes API has not been used in project`** — enable it in Google Cloud. Newly enabled APIs
take a few minutes to propagate and will 403 intermittently until they do.

**Adding a database column does nothing** — `create table if not exists` will not alter a table
that already exists. Add an explicit `alter table ... add column if not exists` in `db.py`.

**Buddy will not answer travel questions** — it needs a location. Open the dashboard and allow
access, or grant Location Services to your terminal and run `venv/bin/python -m engine.locate`.

---

Built at HackRice 16.
