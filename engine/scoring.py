"""Turns one activity row into a productivity probability.

The trained model is loaded once at startup and kept in memory - scoring is ~1ms, which is why
it can live on the request path. When there is no model yet, or the model is unsure, the rules
answer instead. That means the engine works on day one and improves later without the rest of
the system changing.

Falling back is deliberate - a broken model must never take the engine down - but it is also
invisible, so the counters below make it visible. GET /health reports them: `degraded` counts
rows the model could not judge at all (missing, unloadable, or throwing), `unsure` counts rows
it judged too close to call. Rising `degraded` means Buddy is running on the keyword blocklist
and the ML is doing nothing.
"""
from __future__ import annotations

import logging

from engine.config import MODEL_FILE
from ml import rules
from ml.prep import descriptor

log = logging.getLogger("uvicorn.error")

# p within this of 0.5 is a coin flip, so the rules answer instead. Keep it small: a model
# trained on a few hundred rows rarely produces extreme probabilities, and a wide band would
# hand most rows back to the blocklist the model is supposed to improve on.
UNSURE_MARGIN = 0.05

# A model that throws on one row almost always throws on every row - a version-skewed pickle,
# say. After this many in a row we stop calling it and admit we are on the rules, rather than
# retrying forever while /health still claims the model is in use. /model/reload brings it back.
MAX_CONSECUTIVE_FAILURES = 3


class Scorer:
    def __init__(self) -> None:
        self.pipeline = None
        self.version = "rules"
        self.error: str | None = None
        self.calls = 0
        self.degraded = 0  # model could not judge the row at all
        self.unsure = 0    # model judged, too close to call
        self.failures = 0  # consecutive predict failures
        self.load()

    def load(self) -> str:
        """(Re)load the model from disk. Safe to call while running - e.g. after training."""
        self.error = None
        self.failures = 0
        if not MODEL_FILE.exists():
            self.error = f"no model file at {MODEL_FILE.name}"
            log.info("scorer: %s, using rules", self.error)
            return self.version
        try:
            import joblib

            bundle = joblib.load(MODEL_FILE)
            self.pipeline = bundle["pipeline"]
            self.version = bundle.get("version", "model")
            log.info("scorer: loaded %s", self.version)
        except Exception as exc:  # a broken model must never take the engine down
            self.error = f"{type(exc).__name__}: {exc}"
            log.warning("scorer: falling back to rules (%s)", self.error)
            self.pipeline = None
            self.version = "rules"
        return self.version

    def stats(self) -> dict:
        """What /health reports, so silent degradation is visible without reading logs."""
        return {
            "model": self.version,
            "using_model": self.pipeline is not None,
            "scored": self.calls,
            "degraded": self.degraded,
            "unsure": self.unsure,
            "error": self.error,
        }

    def score(self, row: dict) -> dict:
        self.calls += 1
        fallback = rules.score(row)
        if self.pipeline is None:
            self.degraded += 1
            return fallback

        text = descriptor(row)
        if not text:
            # Nothing to read - no domain and no title. The rules see the same emptiness, so
            # this is not the model failing and is not counted against it.
            return fallback
        try:
            p = float(self.pipeline.predict_proba([text])[0][1])
        except Exception as exc:
            self.degraded += 1
            self.failures += 1
            self.error = f"{type(exc).__name__}: {exc}"
            log.warning("scorer: predict failed (%s)", self.error)
            if self.failures >= MAX_CONSECUTIVE_FAILURES:
                self.pipeline = None
                log.error("scorer: disabling %s after %d failures - scoring with ml/rules.py "
                          "until POST /model/reload", self.version, self.failures)
            return fallback

        self.failures = 0

        if abs(p - 0.5) < UNSURE_MARGIN:
            self.unsure += 1
            return {**fallback, "source": f"rules(unsure model p={p:.2f})"}
        return {
            "p": round(p, 3),
            "label": rules.label_for(p),
            "source": self.version,
        }
