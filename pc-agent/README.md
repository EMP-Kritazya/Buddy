# pc-agent/ — PC scrape → label → local model → MATLAB

**Owner:** Suyog  
**Branch:** `Suyog`  
**Platform:** Windows (`ctypes.windll`)

## Your job in the pipeline

```
PC scrape (app, title, idle)
  → light label (kind)
  → Kritazya ml.classify → score 0–100
  → buddy_score.csv  (MATLAB plots this)
  → optional POST /events  (Tiger Data timeline for later Gemini context)
```

**Not your job:** `POST /coach` / talking to Gemini. Sandesh’s MATLAB (or backend) triggers Gemini with Tiger context when the productivity series dips.

## Files

| File | Role |
|---|---|
| `agent.py` | Scrape loop, label, call `ml.classify`, write CSVs, optional `/events` |
| `scrape_log.csv` | Runtime: raw labeled scrapes (debug / model training) |
| `../buddy_score.csv` | Runtime: `timestamp,score,app` for MATLAB |
| `../ml/classify.py` | Kritazya’s local scorer (Layer A rules tonight) |
| `triggers.json` | Kept for the team — **MATLAB / coach side**, not used by this agent anymore |
| `requirements.txt` | `requests` |

## Run

```powershell
cd D:\Buddy\pc-agent
pip install -r requirements.txt
python agent.py --dry-run
```

Against the backend (Tiger `/events`):

```powershell
$env:BUDDY_API = "http://127.0.0.1:8000"
python agent.py
```

| Flag | Effect |
|---|---|
| `--dry-run` | No HTTP; still scrape / label / score / CSVs |
| `--no-events` | CSV only, skip `POST /events` |
| `--api-base URL` | Backend root (same as `BUDDY_API`) |

## Tonight exit

- [ ] Console prints foreground app on change
- [ ] `D:\Buddy\buddy_score.csv` grows (`timestamp,score,app`)
- [ ] `pc-agent/scrape_log.csv` grows with `kind` labels
- [ ] MATLAB can plot the score CSV
- [ ] No `[coach]` lines from this process (that’s intentional)
