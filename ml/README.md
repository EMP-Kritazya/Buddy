# ml/ — Productivity Classifier

**Owner:** Kritazya (P2)  
**Used by:** `backend/main.py` (auto-classify on POST /events), `pc-agent/agent.py` (local scoring)

## What lives here

| File | Purpose |
|---|---|
| `classify.py` | Rule-based scorer (Layer A, ships tonight) + sklearn hook (Layer B, Saturday) |
| `buddy_model.pkl` | _(Saturday only)_ Pre-trained sklearn pipeline — generated separately |

## Scoring rules (Layer A)

| Score | Apps / patterns |
|---|---|
| 75–100 | VS Code, Cursor, MATLAB, Word, Overleaf, Gmail compose, Google Docs |
| 45–74 | Generic Chrome, Slack, Outlook, inbox |
| 0–35 | Games, Discord, Shorts, Instagram, TikTok, Netflix, Steam |
| 70 | YouTube + "tutorial\|lecture" in title |
| 15 | YouTube Shorts |
| 20 | Idle > 60 s during a deadline task |

Returns `Classification(score, label, category, confidence)`.

`label`: `productive | unproductive | mixed | idle | break`

## How to import

```python
from ml.classify import classify

c = classify(app="League of Legends", window_title="League of Legends", idle_s=0, open_tasks=[])
print(c.score, c.label)   # 12  unproductive
```

## Test it

```bash
python ml/classify.py
```

Prints a table of test cases with expected scores.

## Layer B (Saturday, optional)

- Train on synthetic event rows
- Export as `ml/buddy_model.pkl`
- Falls back to Layer A if `confidence < 0.6`

## Tonight exit

- [ ] `classify("League of Legends", "League of Legends")` → score ≈ 12
- [ ] `classify("Code", "buddy — Visual Studio Code")` → score ≈ 85
- [ ] `classify("chrome", "YouTube — tutorial timescaledb")` → score ≈ 70
