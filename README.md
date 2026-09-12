# Buddy — HackRice 16

> You tell Buddy what you owe the day. A PC script watches what you actually do. A local model scores it. If you stay off-task, Gemini knows your goals and talks to you through the speaker on your wrist.

## Quick start

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# PC agent (new terminal)
cd pc-agent && python agent.py

# MATLAB
# Open matlab/plot_score.mlx and run
```

## Repo layout

```
watch/          Arduino firmware (ESP32-S3 LilyGO T-Display-S3)
voice/          ElevenLabs Scribe STT + TTS helper
audio/          Canned WAV fallbacks
backend/        FastAPI — Tiger Data, Gemini, classify
ml/             classify.py — local scoring model
dashboard/      Lovable export
journal/        Markdown templates
pc-agent/       Window logger + trigger → /coach
matlab/         Live score plot
shared/         Schema contracts
```

## Demo loop (6 steps)

1. Hold button → say goals
2. Gemini confirms, stores tasks, suggests order
3. PC logger writes every app to Tiger Data with score 0–100
4. MathWorks plots score live
5. Open a game → after ~45 s of low score, Buddy speaks through the watch
6. Dashboard shows the dip; journal logs the incident

## Failure modes

| Failure | Fallback |
|---|---|
| Venue Wi-Fi | Phone hotspot |
| Tiger Cloud | SQLite (`backend/fallback.db`) |
| ElevenLabs | Canned WAVs in `audio/` |
| Watch battery | USB-C tethered |
| MATLAB | Lovable chart only |
