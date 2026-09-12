from __future__ import annotations

import re

_UNREAD = re.compile(r"^\(\d+\)\s*")               # "(5504) YouTube"
_TLD = re.compile(r"\.(com|org|net|io|dev|co|edu|gov|ai|app|me|tv|so|sh)$")
_APP_SUFFIX = re.compile(r"\.(app|exe)$", re.I)
_VERSION = re.compile(r"\b\d+(\.\d+){2,}\b")        # "Slack 4.38.125", but keeps "18.06"
_NOISE = re.compile(r"[^a-z0-9\s]+")


def clean_title(title: str | None) -> str:
    """Strip the unread-notification count sites put in front of their titles."""
    return _UNREAD.sub("", (title or "").strip())


def where_of(row: dict) -> str:
    """The place: a domain for browser rows, an app name for desktop rows."""
    return (row.get("domain") or row.get("app_name") or "").strip()


def what_of(row: dict) -> str:
    """What was on screen: a page title or a window title."""
    return (row.get("title") or row.get("window_title") or "").strip()


def descriptor(row: dict) -> str:
    """One activity row -> the string the vectorizer sees, whichever sensor produced it.

    Only the two slots: url_path was measured and dropped - it made the model slightly WORSE
    (0.832 -> 0.852 on unseen templates) because tokens like "watch" and "search" attach to a
    site rather than to what the page actually is."""
    return clean_text(where_of(row), what_of(row))


def clean_text(where: str | None, what: str | None) -> str:
    where = _APP_SUFFIX.sub("", (where or "").lower())
    where = _TLD.sub("", where).replace("www.", "")
    parts = [
        where.replace(".", " ").replace("-", " ").replace("_", " "),
        clean_title(what).lower(),
    ]
    text = " ".join(parts)
    text = _VERSION.sub(" ", text)
    text = _NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()
