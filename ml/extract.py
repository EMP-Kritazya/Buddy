# Prepping data for ML training
#
#   python -m ml.extract                                  # your real capture log
#   python -m ml.extract --source ml/datasets/dataset.jsonl   # the generated set
#
# Collapses heartbeats to one row per session, drops rows too short or too empty to mean
# anything, and writes the fields the model is built from. The vectorizer input is derived from
# these same fields at train time, so what you read here is exactly what it learns from.

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from ml.prep import descriptor, what_of

ROOT = Path(__file__).resolve().parent.parent
MIN_SECONDS = 2.0

COLUMNS = ["session_id", "app_name", "app_type", "browser_name", "domain", "title",
           "duration_s", "label"]


def collapse(path: Path) -> list[dict]:
    """Newest row per session_id - the same upsert the database will do."""
    latest: dict[str, dict] = {}
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["session_id"]] = row
    return list(latest.values())


def usable(rows: list[dict]) -> list[dict]:
    """Only settled sessions long enough to mean something."""
    return [r for r in rows
            if r.get("is_final") and r.get("duration_s", 0) >= MIN_SECONDS and descriptor(r)]


def fields(row: dict) -> dict:
    """The row reduced to what the model is built from. Title covers both sensors: a page title
    for a browser tab, a window title for a desktop app."""
    return {
        "session_id": row.get("session_id", ""),
        "app_name": row.get("app_name") or "",
        "app_type": row.get("app_type") or "",
        "browser_name": row.get("browser_name") or "",
        "domain": row.get("domain") or "",
        "title": what_of(row),
        "duration_s": row.get("duration_s", 0),
        "label": row.get("label", ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/sessions.jsonl")
    ap.add_argument("--out", default=None, help="defaults to extracted.tsv beside the source")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    source = ROOT / args.source
    out = Path(args.out) if args.out else source.with_name("extracted.tsv")

    all_rows = collapse(source)
    rows = usable(all_rows)
    print(f"{source.relative_to(ROOT)}: {len(all_rows)} sessions, {len(rows)} usable "
          f"(final, >= {MIN_SECONDS:.0f}s, non-empty)\n")

    print(f"{'APPLICATION':<22} {'APP_TYPE':<9} {'BROWSER':<15} {'DOMAIN':<24} TITLE")
    print("-" * 120)
    for r in rows[: args.limit]:
        f = fields(r)
        print(f"{f['app_name'][:21]:<22} {f['app_type']:<9} {f['browser_name'][:14]:<15} "
              f"{f['domain'][:23]:<24} {f['title'][:44]}")

    with out.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            f = fields(r)
            fh.write("\t".join(str(f[c]).replace("\t", " ") for c in COLUMNS) + "\n")

    texts = [descriptor(r) for r in rows]
    unique = set(texts)
    tokens = collections.Counter()
    for t in texts:
        tokens.update(set(t.split()))
    print(f"\n{len(rows)} rows, {len(unique)} distinct after cleaning "
          f"({len(rows) - len(unique)} duplicates the model would see twice)")
    print(f"vocabulary: {len(tokens)} tokens   most common: "
          f"{', '.join(f'{t}({n})' for t, n in tokens.most_common(10))}")
    if any(f := [r.get("label") for r in rows if r.get("label") is not None]):
        print(f"labels: productive {f.count(1)}   unproductive {f.count(0)}")
    print(f"\nwrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
