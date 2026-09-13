from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, fbeta_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import (
    GroupKFold, GroupShuffleSplit, cross_val_score, train_test_split,
)
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml import rules            # noqa: E402
from ml.prep import descriptor  # noqa: E402

ML_DIR = Path(__file__).resolve().parent
ROOT = ML_DIR.parent
SEED = ML_DIR / "seed.tsv"
GENERATED = ML_DIR / "datasets" / "dataset.jsonl"
CHALLENGE = ML_DIR / "challenge.tsv"
SESSIONS = ROOT / "data" / "sessions.jsonl"
MODEL_OUT = ML_DIR / "model.joblib"

CONFIDENT_HIGH = 0.85  # only auto-label real rows the rules are sure about
CONFIDENT_LOW = 0.15


def row_from(source: str, where: str, what: str) -> dict:
    """Build the same dict shape the sensors send, so training uses the live code path."""
    if source == "desktop":
        return {"app_name": where, "window_title": what, "app_type": "desktop"}
    return {"domain": where, "title": what, "app_type": "browser"}


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_seed() -> tuple[list[str], list[int], list[str]]:
    texts, labels, origins = [], [], []
    for r in read_tsv(SEED):
        texts.append(descriptor(row_from(r["source"], r["where"], r["what"])))
        labels.append(int(r["label"]))
        origins.append("seed")
    return texts, labels, origins


def load_generated(seen: set[str]) -> tuple[list[str], list[int], list[str], list[str]]:
    """Generated rows carry the template that produced them, which lets us hold out whole
    phrasings later instead of only random rows."""
    texts, labels, groups = [], [], []
    if not GENERATED.exists():
        return texts, labels, groups, []
    for line in GENERATED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = descriptor(row)
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
        labels.append(int(row["label"]))
        groups.append(row["template"])
    return texts, labels, ["generated"] * len(texts), groups


def load_real(seen: set[str]) -> tuple[list[str], list[int], list[str]]:
    """Collapsed final sessions, labelled by the rules only where they are confident."""
    texts, labels, origins = [], [], []
    if not SESSIONS.exists():
        return texts, labels, origins
    latest: dict[str, dict] = {}
    for line in SESSIONS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["session_id"]] = row
    for row in latest.values():
        if not row.get("is_final") or row.get("duration_s", 0) < 2:
            continue
        text = descriptor(row)
        if not text or text in seen:
            continue
        p = rules.score(row)["p"]
        if p >= CONFIDENT_HIGH:
            labels.append(1)
        elif p <= CONFIDENT_LOW:
            labels.append(0)
        else:
            continue  # the rules are unsure; a guess here would poison the model
        seen.add(text)
        texts.append(text)
        origins.append("real")
    return texts, labels, origins


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),   # bigrams catch "pull request", "official video"
            sublinear_tf=True,
            min_df=1,
            strip_accents="unicode",
        )),
        ("clf", LogisticRegression(
            class_weight="balanced",  # the seed set has more productive rows than not
            C=4.0,
            max_iter=1000,
        )),
    ])


def report(name: str, x_tr, y_tr, x_te, y_te, caveat: str) -> dict:
    """Fit on the training half and score the held-out half.

    Positive class = productive. Precision says how much of what it CALLS productive really is;
    recall says how much of the truly productive work it CATCHES. Recall matters more here: a
    missed productive row is Buddy interrupting you while you work, which is the failure a desk
    mentor cannot afford. F2 weights recall twice as heavily as precision for that reason.
    """
    pipe = build_pipeline().fit(x_tr, y_tr)
    pred = pipe.predict(x_te)
    proba = pipe.predict_proba(x_te)[:, 1]

    print(f"\n{name}   train {len(x_tr)} / test {len(x_te)}")
    print(f"  ({caveat})")
    print(f"  accuracy  {accuracy_score(y_te, pred):.3f}     "
          f"precision {precision_score(y_te, pred, zero_division=0):.3f}     "
          f"recall {recall_score(y_te, pred, zero_division=0):.3f}")
    print(f"  f1        {fbeta_score(y_te, pred, beta=1, zero_division=0):.3f}     "
          f"f2        {fbeta_score(y_te, pred, beta=2, zero_division=0):.3f}     "
          f"roc auc {roc_auc_score(y_te, proba):.3f}")

    metrics = {
        "accuracy": round(accuracy_score(y_te, pred), 3),
        "precision": round(precision_score(y_te, pred, zero_division=0), 3),
        "recall": round(recall_score(y_te, pred, zero_division=0), 3),
        "f1": round(fbeta_score(y_te, pred, beta=1, zero_division=0), 3),
        "f2": round(fbeta_score(y_te, pred, beta=2, zero_division=0), 3),
        "roc_auc": round(roc_auc_score(y_te, proba), 3),
    }
    tn, fp, fn, tp = confusion_matrix(y_te, pred, labels=[0, 1]).ravel()
    print(f"                      predicted not-productive   predicted productive")
    print(f"  actually not-productive          {tn:>5}                  {fp:>5}   <- false alarms")
    print(f"  actually productive              {fn:>5}                  {tp:>5}")
    print(f"                                     ^ nags you while working")
    return metrics


def top_tokens(pipe: Pipeline, n: int = 12) -> tuple[list[str], list[str]]:
    names = pipe.named_steps["tfidf"].get_feature_names_out()
    weights = pipe.named_steps["clf"].coef_[0]
    order = weights.argsort()
    return [names[i] for i in order[-n:][::-1]], [names[i] for i in order[:n]]


def main() -> None:
    texts, labels, origins = load_seed()
    seen = set(texts)
    gen_t, gen_l, gen_o, gen_groups = load_generated(seen)
    real_t, real_l, real_o = load_real(seen)
    texts += gen_t + real_t
    labels += gen_l + real_l
    origins += gen_o + real_o

    print(f"training rows: {len(texts)}  (seed {origins.count('seed')}, "
          f"generated {origins.count('generated')}, real {origins.count('real')})")
    print(f"  productive {labels.count(1)}   unproductive {labels.count(0)}")

    
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=42)
    scores = {"random_80_20": report(
        "random 80/20 split", X_train, y_train, X_test, y_test,
        "rows from the same template land in both halves, so this flatters the model")}

    if gen_groups:
        # Hold out whole templates: the test half contains phrasings never seen in training.
        split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        tr_idx, te_idx = next(split.split(gen_t, gen_l, groups=gen_groups))
        scores["by_template_80_20"] = report(
            "by-template 80/20 split",
            [gen_t[i] for i in tr_idx], [gen_l[i] for i in tr_idx],
            [gen_t[i] for i in te_idx], [gen_l[i] for i in te_idx],
            "whole phrasings held out - the number to trust")

        g_acc = cross_val_score(build_pipeline(), gen_t, gen_l, groups=gen_groups,
                                cv=GroupKFold(n_splits=5), scoring="accuracy")
        scores["by_template_cv_accuracy"] = round(float(g_acc.mean()), 3)
        print(f"\n5-fold by-template CV: accuracy {g_acc.mean():.3f} (+/-{g_acc.std():.3f}) "
              f"- the spread is how much the split choice matters")

    pipe = build_pipeline()

    pipe.fit(texts, labels)  # the shipped model sees every row; the scores above came from holdouts

    # --- the honest test: cases where the domain or app alone is misleading ---
    rows = read_tsv(CHALLENGE)
    model_hits = rule_hits = 0
    print(f"\nheld-out challenge set ({len(rows)} rows the model never saw):")
    print(f"  {'place':<22} {'truth':<13} {'model':<14} {'rules':<13} verdict")
    for r in rows:
        row = row_from(r["source"], r["where"], r["what"])
        p_model = float(pipe.predict_proba([descriptor(row)])[0][1])
        p_rules = rules.score(row)["p"]
        truth = int(r["label"])
        ok_m = int(p_model >= 0.5) == truth
        ok_r = int(p_rules >= 0.5) == truth
        model_hits += ok_m
        rule_hits += ok_r
        verdict = "model wins" if ok_m and not ok_r else ("rules win" if ok_r and not ok_m else "")
        print(f"  {r['where'][:21]:<22} {'productive' if truth else 'unproductive':<13} "
              f"{p_model:.2f} {'OK ' if ok_m else 'MISS':<9} {p_rules:.2f} {'OK ' if ok_r else 'MISS':<8} {verdict}")
    print(f"\n  model {model_hits}/{len(rows)}    rules {rule_hits}/{len(rows)}")

    productive, unproductive = top_tokens(pipe)
    print(f"\ntop 'productive' tokens:   {', '.join(productive)}")
    print(f"top 'unproductive' tokens: {', '.join(unproductive)}")

    version = f"tfidf-logreg-{datetime.now(timezone.utc):%Y%m%d-%H%M}"
    joblib.dump({"pipeline": pipe, "version": version, "trained_at": datetime.now(timezone.utc).isoformat(),
                 "n_samples": len(texts), "scores": scores}, MODEL_OUT)
    print(f"\nsaved {MODEL_OUT.relative_to(ROOT)}  version={version}")


if __name__ == "__main__":
    main()
