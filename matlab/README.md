# matlab/ — Live Productivity Score Plot

**Owner:** Sandesh (P4)  
**Dependency:** `buddy_score.csv` written by `pc-agent/agent.py`

## What lives here

| File | Purpose |
|---|---|
| `plot_score.m` | Live-updating MATLAB plot; upgrades to API on Saturday |

## How it works

**Tonight (CSV mode):**
Reads `../buddy_score.csv` every 2 s and re-plots. The red dashed line at y=35 marks the slump threshold.

**Saturday (API mode):**
Calls `webread('http://127.0.0.1:8000/stats')` every 5 s for time-bucketed averages. Falls back to CSV if the API is unreachable.

## How to run

Open `plot_score.m` in MATLAB and press **Run** (or click the Live Script Run button if using `.mlx`).  
Full-screen on a second monitor for judging.

```matlab
% Or from the MATLAB command window:
run('matlab/plot_score.m')
```

## Python matplotlib fallback

If MATLAB is unavailable, run this one-liner from the project root:

```bash
python -c "
import csv, time, matplotlib.pyplot as plt
plt.ion(); fig, ax = plt.subplots()
while True:
    rows = list(csv.DictReader(open('buddy_score.csv')))
    if rows:
        ax.cla(); ax.set_ylim(0,100)
        ax.axhline(35, color='red', linestyle='--')
        ax.plot([r['timestamp'][-8:-3] for r in rows], [int(r['score']) for r in rows])
        fig.canvas.draw(); plt.pause(2)
    time.sleep(2)
"
```

## Tonight exit

- [ ] MATLAB plot window opens and updates as `buddy_score.csv` grows
- [ ] Red dashed line visible at y=35
- [ ] Plot does not crash when CSV is empty (wait for first data row)
