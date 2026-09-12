# dashboard/ — Lovable Frontend

**Owner:** Basanta (P3)  
**Depends on:** `backend/main.py` running (falls back to fixture data when offline)

## What lives here

| File | Purpose |
|---|---|
| `index.html` | Self-contained dashboard — Chart.js score timeline, tasks, live score, incidents |

## What it shows

| Panel | Source |
|---|---|
| Score over time (line chart) | `GET /stats` → time-bucketed averages |
| Current score + current app | `GET /events` (latest row) |
| Today's tasks | `GET /tasks` |
| Coaching incidents | `GET /events` filtered to score < 35 |

## Fixture data

`index.html` renders fixture data immediately so the dashboard looks good even before the backend is up. Once the API responds, real data overwrites it. No white screen during demos.

## How to open locally

Just open `dashboard/index.html` in Chrome. No server needed.

## Point at the backend

Edit line near the top of `index.html`:

```js
const API = 'http://LAPTOP_IP:8000';
```

Replace `LAPTOP_IP` with the demo laptop's IP on the venue Wi-Fi (or `127.0.0.1` if running on the same machine).

## Lovable integration (Saturday)

Export the Lovable project here and commit. Keep the same `API` constant so it auto-wires to the running backend.

## Tonight exit

- [ ] `index.html` opens in browser and shows fixture score chart + two tasks + one incident
- [ ] No console errors
- [ ] `GET /stats` returns data → chart updates without refresh

## Saturday exit

- [ ] Chart animates live as `pc-agent/agent.py` generates events
- [ ] Tasks update when Buddy captures new goals via the watch
- [ ] Incident list shows the game-during-senior-design slump event
