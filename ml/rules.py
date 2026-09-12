from __future__ import annotations

import re

from ml.prep import clean_title, what_of, where_of

# Browser
PRODUCTIVE_DOMAINS = {
    "github.com", "gitlab.com", "stackoverflow.com", "stackexchange.com",
    "developer.mozilla.org", "docs.python.org", "scikit-learn.org", "pypi.org",
    "readthedocs.io", "arxiv.org", "scholar.google.com", "overleaf.com",
    "canvas.instructure.com", "colab.research.google.com", "kaggle.com",
    "notion.so", "linear.app", "atlassian.net", "figma.com", "mathworks.com",
    "docs.google.com", "sheets.google.com", "leetcode.com", "chatgpt.com", "claude.ai",
}
UNPRODUCTIVE_DOMAINS = {
    "youtube.com", "reddit.com", "instagram.com", "tiktok.com", "twitter.com", "x.com",
    "facebook.com", "netflix.com", "twitch.tv", "primevideo.com", "hulu.com",
    "9gag.com", "pinterest.com", "snapchat.com",
}
NEUTRAL_DOMAINS = {"google.com", "duckduckgo.com", "bing.com", "mail.google.com", "outlook.com"}

# Apps
PRODUCTIVE_APPS = {
    "code", "visual studio code", "cursor", "xcode", "pycharm", "intellij idea", "webstorm",
    "clion", "rider", "android studio", "sublime text", "neovim", "vim", "emacs",
    "terminal", "iterm2", "warp", "ghostty", "kitty", "alacritty",
    "matlab", "rstudio", "jupyter", "arduino ide", "platformio", "docker desktop",
    "figma", "notion", "obsidian", "microsoft word", "microsoft excel", "microsoft powerpoint",
    "pages", "numbers", "keynote", "preview", "zotero", "postman", "tableplus", "dbeaver",
}
UNPRODUCTIVE_APPS = {
    "steam", "epic games launcher", "battle net", "league of legends", "valorant", "minecraft",
    "netflix", "hulu", "disney+", "vlc", "quicktime player", "twitch", "tiktok",
    "instagram", "whatsapp", "messenger", "snapchat",
}
# Places that are work for some people and a hole for others; the title decides.
NEUTRAL_APPS = {
    "google chrome", "safari", "firefox", "arc", "brave browser", "microsoft edge",
    "slack", "discord", "zoom", "microsoft teams", "messages", "mail", "spotify", "music",
    "finder", "system settings", "calendar", "notes", "reminders",
}

# What's on screen
LEARNING = re.compile(
    r"lecture|tutorial|course|documentation|\bdocs\b|how to|crash course|mit ocw|"
    r"khan academy|freecodecamp|conference talk|paper|thesis|assignment|homework|"
    r"\.py\b|\.js\b|\.ts\b|\.ipynb\b|\.tex\b|\.c\b|\.cpp\b|\.java\b|\.rs\b|\.go\b|"
    r"pull request|merge request|code review|standup|sprint|debug|stack trace",
    re.I,
)
LEISURE = re.compile(
    r"shorts|meme|funny|prank|reaction|vlog|highlights|trailer|music video|official video|"
    r"full episode|gameplay|let's play|speedrun|stream|comedy|latent|season \d|episode \d",
    re.I,
)

def score(row: dict) -> dict:
    """Score one activity row - browser tab or desktop window.

    Returns p in 0..1 (how productive) and a label that is only ever "productive" or
    "unproductive". Screensaver and login-window rows are the sensor's job to not send."""
    place = where_of(row).lower().removeprefix("www.")
    title = clean_title(what_of(row))

    base = 0.5
    if place in PRODUCTIVE_DOMAINS or place in PRODUCTIVE_APPS:
        base = 0.9
    elif place in UNPRODUCTIVE_DOMAINS or place in UNPRODUCTIVE_APPS:
        base = 0.1
    elif place in NEUTRAL_DOMAINS:
        base = 0.6
    elif place in NEUTRAL_APPS:
        base = 0.5

    # The window title is the tiebreaker, and it can overrule the place in both directions.
    if LEARNING.search(title):
        base = max(base, 0.8)
    elif LEISURE.search(title) and place not in PRODUCTIVE_DOMAINS and place not in PRODUCTIVE_APPS:
        base = min(base, 0.15)

    return {"p": round(base, 3), "label": label_for(base), "source": "rules"}


def label_for(p: float) -> str:
    """Two labels, nothing else. p is the confidence; the label is just which side of 0.5."""
    return "productive" if p >= 0.5 else "unproductive"
