"""Turns one activity row into a productivity probability.

The trained model is loaded once at startup and kept in memory - scoring is ~1ms, which is why
it can live on the request path. When there is no model yet, or the model is unsure, the rules
answer instead. That means the engine works on day one and improves later without the rest of
the system changing.
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


class Scorer:
    def __init__(self) -> None:
        self.pipeline = None
        self.version = "rules"
        self.load()

    def load(self) -> str:
        """(Re)load the model from disk. Safe to call while running - e.g. after training."""
        if not MODEL_FILE.exists():
            log.info("scorer: no model at %s, using rules", MODEL_FILE.name)
            return self.version
        try:
            import joblib

            bundle = joblib.load(MODEL_FILE)
            self.pipeline = bundle["pipeline"]
            self.version = bundle.get("version", "model")
            log.info("scorer: loaded %s", self.version)
        except Exception as exc:  # a broken model must never take the engine down
            log.warning("scorer: falling back to rules (%s)", exc)
            self.pipeline = None
            self.version = "rules"
        return self.version

    def score(self, row: dict) -> dict:
        fallback = rules.score(row)
        if self.pipeline is None:
            return fallback

        text = descriptor(row)
        if not text:
            return fallback
        try:
            p = float(self.pipeline.predict_proba([text])[0][1])
        except Exception as exc:
            log.warning("scorer: predict failed (%s)", exc)
            return fallback

        if abs(p - 0.5) < UNSURE_MARGIN:
            return {**fallback, "source": f"rules(unsure model p={p:.2f})"}
        return {
            "p": round(p, 3),
            "label": rules.label_for(p),
            "source": self.version,
        }
