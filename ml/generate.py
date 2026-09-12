"""Generate a labelled training set in the real session-row shape.

    python -m ml.generate --n 1000

Every row is built by a named TEMPLATE that carries its own label, so labels come from the
generator's intent - never from rules.py. That keeps the model from simply re-learning the
blocklist it is supposed to beat.

The template name is stored on each row so training can hold out WHOLE TEMPLATES and measure
generalisation to phrasings it has never seen. Without that, a synthetic set flatters itself.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ml" / "datasets" / "dataset.jsonl"

# --------------------------------------------------------------------------- vocabulary
LANGS = ["python", "javascript", "typescript", "rust", "go", "java", "c++", "swift", "sql", "bash"]
TECH = ["fastapi", "asyncio", "sqlalchemy", "timescaledb", "postgres", "docker", "kubernetes",
        "react", "numpy", "pandas", "scikit-learn", "pytorch", "tensorflow", "opencv", "esp32",
        "i2s audio", "bluetooth le", "webrtc", "tf-idf", "logistic regression", "random forest",
        "transformers", "embeddings", "kafka", "redis", "nginx", "websockets", "chrome extension"]
PROBLEMS = ["memory leak", "race condition", "deadlock", "cors error", "timeout", "type error",
            "connection pool exhausted", "slow query", "flaky test", "import cycle"]
REPOS = ["buddy", "activity-logger", "mentor-engine", "esp32-voice", "timeseries-api",
         "senior-design", "portfolio", "dotfiles", "hackrice-16"]
USERS = ["kritazya", "rahulm", "sofia-dev", "anita", "leo", "tarunk", "meiling"]
ORGS = ["scikit-learn", "fastapi", "pytorch", "timescale", "espressif", "vercel"]
COURSES = ["MIT 18.06", "Stanford CS229", "CS231n", "COMP 322", "MATH 2415", "ECE 445",
           "Berkeley CS61A", "COMP 540", "STAT 310"]
TOPICS = ["linear algebra", "backpropagation", "dynamic programming", "operating systems",
          "signal processing", "probability", "graph theory", "compilers", "control systems"]
TEACHERS = ["3Blue1Brown", "Andrej Karpathy", "Fireship", "freeCodeCamp", "Computerphile",
            "Two Minute Papers", "sentdex", "Tech With Tim", "ArjanCodes"]
SUBS_WORK = ["learnpython", "MachineLearning", "learnprogramming", "datascience", "rust",
             "ExperiencedDevs", "cscareerquestions", "embedded"]
PAPERS = ["attention is all you need", "deep residual learning", "a survey of activity recognition",
          "efficient transformers", "batch normalization", "adam optimizer"]

ARTISTS = ["Coldplay", "Taylor Swift", "Arijit Singh", "The Weeknd", "Drake", "Dua Lipa",
           "AP Dhillon", "Diljit Dosanjh", "Imagine Dragons", "Karan Aujla"]
SONGS = ["Viva La Vida", "Cruel Summer", "Blinding Lights", "Kesariya", "Levitating",
         "Brown Munde", "Believer", "Softly", "Paradise"]
SHOWS = ["Stranger Things", "Breaking Bad", "The Office", "Money Heist", "Squid Game",
         "Wednesday", "Peaky Blinders", "Friends", "Dark"]
GAMES = ["Valorant", "League of Legends", "Minecraft", "CS2", "Fortnite", "Apex Legends",
         "GTA V", "Elden Ring", "FIFA 26", "Rocket League"]
FUN_CREATORS = ["MrBeast", "CarryMinati", "Dude Perfect", "Markiplier", "Technoblade",
                "Samay Raina", "Ashish Chanchlani"]
CLICKBAIT = ["I survived 50 hours in a box", "we tried the impossible challenge",
             "reacting to my old videos", "worst roommate stories", "24 hours in the airport",
             "spending $10000 in 10 minutes", "my honest apartment tour"]
SUBS_FUN = ["memes", "funny", "aww", "nba", "gaming", "dankmemes", "pcmasterrace",
            "nextfuckinglevel", "cricket"]
# Posts are paired to their subreddit: an incoherent pairing would drop work vocabulary into an
# unproductive row and teach the model the opposite of what we mean.
FUN_POSTS_BY_SUB = {
    "memes": ["monday morning mood", "nobody: absolutely nobody:", "this meme is too real"],
    "dankmemes": ["deep fried friday", "cursed image thread", "no context memes"],
    "funny": ["my dog stole the remote", "worst haircut ever", "grandma texting fails"],
    "aww": ["this cat is me at 3am", "rescued puppy first day home", "baby otter holding hands"],
    "nba": ["game thread lakers vs celtics", "top plays of the week", "trade rumors megathread"],
    "cricket": ["match thread india vs australia", "greatest innings of all time"],
    "gaming": ["my new battlestation", "finally beat the final boss", "worst ui in a modern game"],
    "pcmasterrace": ["my new battlestation", "cable management attempt", "rgb overload build"],
    "nextfuckinglevel": ["this street performer is insane", "found this in my attic"],
}
FUN_POSTS = [p for posts in FUN_POSTS_BY_SUB.values() for p in posts]
SEARCH_FUN = ["nba scores tonight", "cheap flights to cancun", "iphone 18 price",
              "movie showtimes near me", "best biryani houston", "ipl points table"]

FILES = ["train.py", "session.js", "queue.js", "trigger.py", "app.py", "store.py", "main.py",
         "model.ipynb", "schema.sql", "README.md", "Dockerfile", "buddy.ino", "plot_score.m",
         "index.html", "styles.css", "agent.swift", "prep.py"]
PROJECTS = ["Buddy", "hackrice", "senior-design", "portfolio", "esp32-voice"]
CMDS = ["uvicorn engine.app:app", "pytest -q", "npm run dev", "git rebase -i main",
        "docker compose up", "python -m ml.train", "tail -f engine.log", "ssh pi@buddy.local",
        "psql buddy", "arduino-cli compile", "git log --oneline"]
CHANNELS_WORK = ["#buddy-dev", "#standup", "#code-review", "#help-python", "#backend", "#general"]
CHANNELS_FUN = ["#gaming", "#memes", "#valorant-lfg", "#music", "#random", "#anime"]
WORKSPACES = ["HackRice", "Rice CS", "Buddy Team", "Senior Design"]
DOCS = ["Senior design report", "Lab writeup", "Meeting notes", "Sprint plan",
        "Demo script", "Interview prep"]
SHEET_DOCS = ["experiment results", "budget", "grade tracker", "benchmark timings",
              "survey responses", "parts list"]
PDFS = ["attention_is_all_you_need.pdf", "lecture_notes_week3.pdf", "syllabus.pdf",
        "paper_draft.pdf", "datasheet_esp32.pdf", "problem_set_4.pdf"]
MEETINGS = ["Senior Design weekly", "HackRice standup", "COMP 322 lecture", "advisor check-in",
            "sprint planning", "office hours"]
PEOPLE = ["mom", "dad", "sister", "Rahul", "Sofia", "grandma", "Leo"]
EDITORS = ["Visual Studio Code", "Cursor", "PyCharm", "Xcode", "Sublime Text", "Neovim"]
TERMINALS = ["Terminal", "iTerm2", "Warp", "Ghostty"]
OFFICE = [("Microsoft Word", "docx"), ("Microsoft Excel", "xlsx"),
          ("Microsoft PowerPoint", "pptx"), ("Pages", "pages"), ("Numbers", "numbers")]
DOCSITES = [("docs.python.org", "Python"), ("scikit-learn.org", "scikit-learn"),
            ("fastapi.tiangolo.com", "FastAPI"), ("developer.mozilla.org", "MDN"),
            ("pytorch.org", "PyTorch"), ("docs.timescale.com", "Timescale"),
            ("reactjs.org", "React"), ("docs.docker.com", "Docker")]

R = random.Random(7)
pick = lambda xs: R.choice(xs)
_stem = lambda name: name.rsplit('.', 1)[0]


# --------------------------------------------------------------------------- templates
def browser(domain, title, path="/", audible=False):
    return {"kind": "browser", "where": domain, "what": title, "path": path, "audible": audible}


def desktop(app, window):
    return {"kind": "desktop", "where": app, "what": window, "path": None, "audible": False}


TEMPLATES: dict[str, tuple[int, callable]] = {
    # name: (label, builder)   1 = productive, 0 = unproductive
    "gh_repo":      (1, lambda: browser("github.com", f"{pick(USERS)}/{pick(REPOS)}: {pick(TECH)} for {pick(TOPICS)}", "/")),
    "gh_pr":        (1, lambda: browser("github.com", f"Pull Request #{R.randint(2, 300)}: fix {pick(PROBLEMS)} by {pick(USERS)}", "/pull")),
    "gh_file":      (1, lambda: browser("github.com", f"{pick(REPOS)}/{pick(FILES)} at main", "/blob")),
    "gh_issues":    (1, lambda: browser("github.com", f"Issues - {pick(ORGS)}/{pick(REPOS)}", "/issues")),
    "stackoverflow":(1, lambda: browser("stackoverflow.com", f"{pick(LANGS)} - how to fix {pick(PROBLEMS)} in {pick(TECH)} - Stack Overflow", "/questions")),
    "docs":         (1, lambda: (lambda d: browser(d[0], f"{pick(TECH)} - {d[1]} documentation", "/docs"))(pick(DOCSITES))),
    "yt_lecture":   (1, lambda: browser("youtube.com", f"{pick(COURSES)} Lecture {R.randint(1, 20)}: {pick(TOPICS)} - YouTube", "/watch", True)),
    "yt_tutorial":  (1, lambda: browser("youtube.com", f"{pick(TEACHERS)} - {pick(TECH)} tutorial for beginners - YouTube", "/watch", True)),
    "search_work":  (1, lambda: browser("google.com", f"{pick(LANGS)} {pick(TECH)} {pick(PROBLEMS)} - Google Search", "/search")),
    "leetcode":     (1, lambda: browser("leetcode.com", f"{pick(['Two Sum','Merge Intervals','LRU Cache','Word Ladder','Course Schedule'])} - LeetCode", "/problems")),
    "colab":        (1, lambda: browser("colab.research.google.com", f"{_stem(pick(FILES))}.ipynb - Colab", "/drive")),
    "overleaf":     (1, lambda: browser("overleaf.com", f"{pick(DOCS)} - Overleaf, Online LaTeX Editor", "/project")),
    "canvas":       (1, lambda: browser("canvas.instructure.com", f"{pick(COURSES)} - Assignment {R.randint(1, 9)}", "/courses")),
    "arxiv":        (1, lambda: browser("arxiv.org", f"[{R.randint(2301, 2609)}.{R.randint(1000, 9999)}] {pick(PAPERS)}", "/abs")),
    "gdocs":        (1, lambda: browser("docs.google.com", f"{pick(DOCS)} - Google Docs", "/document")),
    "reddit_work":  (1, lambda: browser("reddit.com", f"r/{pick(SUBS_WORK)} - how do I use {pick(TECH)} with {pick(LANGS)}", "/r")),
    "llm_chat":     (1, lambda: browser(pick(["chatgpt.com", "claude.ai"]), f"debugging {pick(PROBLEMS)} in {pick(TECH)}", "/chat")),
    "figma_web":    (1, lambda: browser("figma.com", f"{pick(PROJECTS)} dashboard - Figma", "/file")),

    "yt_music":     (0, lambda: browser("youtube.com", f"{pick(ARTISTS)} - {pick(SONGS)} (Official Video) - YouTube", "/watch", True)),
    "yt_fun":       (0, lambda: browser("youtube.com", f"{pick(FUN_CREATORS)} - {pick(CLICKBAIT)} - YouTube", "/watch", True)),
    "yt_game":      (0, lambda: browser("youtube.com", f"{pick(GAMES)} ranked gameplay highlights - YouTube", "/watch", True)),
    "yt_shorts":    (0, lambda: browser("youtube.com", f"#shorts {pick(FUN_POSTS)}", "/shorts", True)),
    "reddit_fun":   (0, lambda: (lambda sub: browser("reddit.com", f"r/{sub} - {pick(FUN_POSTS_BY_SUB[sub])}", "/r"))(pick(SUBS_FUN))),
    "netflix_web":  (0, lambda: browser("netflix.com", f"{pick(SHOWS)} season {R.randint(1, 5)} - Netflix", "/watch", True)),
    "twitch_web":   (0, lambda: browser("twitch.tv", f"{pick(FUN_CREATORS)} playing {pick(GAMES)} - Twitch", "/stream", True)),
    "instagram":    (0, lambda: browser("instagram.com", pick(["Instagram", "Reels", "Explore - Instagram"]), "/")),
    "tiktok":       (0, lambda: browser("tiktok.com", "For You - TikTok", "/foryou", True)),
    "twitter":      (0, lambda: browser(pick(["twitter.com", "x.com"]), pick(["Home / X", f"{pick(FUN_CREATORS)} on X"]), "/home")),
    "search_fun":   (0, lambda: browser("google.com", f"{pick(SEARCH_FUN)} - Google Search", "/search")),
    "shopping":     (0, lambda: browser("amazon.com", f"Amazon.com: {pick(['gaming mouse','hoodie','airpods case','desk lamp'])}", "/dp")),
    "sports_web":   (0, lambda: browser("espn.com", f"{pick(['NBA','NFL','Cricket'])} scores and standings - ESPN", "/scores")),

    "editor":       (1, lambda: desktop(pick(EDITORS), f"{pick(FILES)} - {pick(PROJECTS)}")),
    "terminal":     (1, lambda: desktop(pick(TERMINALS), f"{pick(PROJECTS)} - {pick(CMDS)}")),
    "matlab":       (1, lambda: desktop("MATLAB", f"{pick(['plot_score.m','analysis.m','filter_design.m'])} - MATLAB")),
    "arduino":      (1, lambda: desktop("Arduino IDE", f"{pick(['buddy.ino','blink.ino','i2s_test.ino'])} - Arduino IDE")),
    "office":       (1, lambda: (lambda o: desktop(o[0], f"{pick(SHEET_DOCS if o[1] in ('xlsx', 'numbers') else DOCS)}.{o[1]}"))(pick(OFFICE))),
    "preview_pdf":  (1, lambda: desktop("Preview", pick(PDFS))),
    "comms_work":   (1, lambda: desktop(pick(["Slack", "Microsoft Teams", "Discord"]), f"{pick(CHANNELS_WORK)} - {pick(WORKSPACES)}")),
    "zoom_work":    (1, lambda: desktop("Zoom", f"{pick(MEETINGS)}")),
    "devtool":      (1, lambda: desktop(pick(["Postman", "Docker Desktop", "TablePlus", "DBeaver", "Notion", "Obsidian", "Figma"]), f"{pick(PROJECTS)} - {pick(['API','containers','postgres','notes','board'])}")),
    "jupyter":      (1, lambda: desktop("Jupyter", f"{_stem(pick(FILES))}.ipynb")),

    "game_app":     (0, lambda: (lambda g: desktop(g, g))(pick(GAMES))),
    "steam":        (0, lambda: desktop("Steam", pick(["Steam", "Store - Steam", "Library - Steam", f"{pick(GAMES)} - Steam"]))),
    "media_app":    (0, lambda: desktop(pick(["Netflix", "VLC", "QuickTime Player"]), f"{pick(SHOWS).replace(' ', '.')}.S0{R.randint(1,4)}E0{R.randint(1,9)}.mkv")),
    "comms_fun":    (0, lambda: desktop("Discord", f"{pick(CHANNELS_FUN)} - {pick(['Valorant Squad','Chill Zone','Gamers United'])}")),
    "music_app":    (0, lambda: desktop(pick(["Spotify", "Music"]), f"{pick(ARTISTS)} - {pick(SONGS)}")),
    "messaging":    (0, lambda: desktop(pick(["Messages", "WhatsApp"]), f"{pick(PEOPLE)}")),
    "photos":       (0, lambda: desktop("Photos", f"{pick(['Summer 2025','Trip to Austin','Screenshots'])}")),
    "social_app":   (0, lambda: desktop(pick(["TikTok", "Instagram", "Twitch"]), pick(["For You", "Feed", "Following"]))),
    "zoom_personal":(0, lambda: desktop("Zoom", f"family call with {pick(PEOPLE)}")),
}

PRODUCTIVE = [k for k, v in TEMPLATES.items() if v[0] == 1]
UNPRODUCTIVE = [k for k, v in TEMPLATES.items() if v[0] == 0]


def duration_for(label: int) -> float:
    """Work happens in long blocks, distraction in bursts - with plenty of overlap."""
    mean = 6.0 if label else 5.3  # log-seconds
    return round(min(max(R.lognormvariate(mean, 0.9), 3.0), 3600.0), 3)


def make_row(i: int, name: str) -> dict:
    label, build = TEMPLATES[name]
    spec = build()
    seconds = duration_for(label)
    start = datetime.now(timezone.utc) - timedelta(
        days=R.randint(0, 13), hours=R.randint(8, 23), minutes=R.randint(0, 59))
    title = spec["what"]
    if spec["kind"] == "browser" and R.random() < 0.12:
        title = f"({R.randint(1, 9000)}) {title}"  # the unread count sites prepend

    row = {
        "session_id": f"gen-{i:05d}",
        "start_ts": start.isoformat().replace("+00:00", "Z"),
        "end_ts": (start + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z"),
        "duration_s": seconds,
        "app_type": spec["kind"],
        "window_title": "" if spec["kind"] == "browser" else spec["what"],
        "browser_name": "Google Chrome" if spec["kind"] == "browser" else None,
        "app_name": "Google Chrome" if spec["kind"] == "browser" else spec["where"],
        "tab_id": R.randint(1, 400) if spec["kind"] == "browser" else None,
        "domain": spec["where"] if spec["kind"] == "browser" else None,
        "title": title if spec["kind"] == "browser" else None,
        "url_path": spec["path"],
        "end_reason": pick(["tab_switch", "navigation", "window_blur", "tab_closed", "idle"]),
        "is_final": True,
        "audible": spec["audible"],
        "tz_offset_min": -300,
        "client": {"ext_version": "0.1.0", "device_id": "synthetic"},
        # training columns
        "label": label,
        "template": name,
    }
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    args = ap.parse_args()

    from ml.prep import descriptor

    rows, seen = [], set()
    attempts = 0
    while len(rows) < args.n and attempts < args.n * 60:
        attempts += 1
        # alternate classes so the set stays balanced without post-hoc trimming
        pool = PRODUCTIVE if len(rows) % 2 == 0 else UNPRODUCTIVE
        row = make_row(len(rows), pick(pool))
        text = descriptor(row)
        if not text or text in seen:
            continue  # duplicates teach nothing and inflate every score
        seen.add(text)
        rows.append(row)

    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"{len(rows)} rows -> {OUT.relative_to(ROOT)}   (unique descriptors, {attempts} draws)")
    print(f"  productive {sum(r['label'] for r in rows)}   unproductive {sum(1 - r['label'] for r in rows)}")
    print(f"  browser {sum(r['app_type'] == 'browser' for r in rows)}   desktop {sum(r['app_type'] == 'desktop' for r in rows)}")
    print(f"  templates {len(set(r['template'] for r in rows))}")
    print("\nsample:")
    for row in R.sample(rows, 8):
        where = row["domain"] or row["app_name"]
        what = row["title"] or row["window_title"]
        print(f"  [{row['label']}] {row['template']:<14} {where:<24} {what[:46]}")


if __name__ == "__main__":
    main()
