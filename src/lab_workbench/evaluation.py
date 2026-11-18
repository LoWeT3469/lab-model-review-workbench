"""Offline replay of label feedback and a two-stage routing policy."""

import numpy as np

from .schema import REVIEW_THRESHOLD
from .synthetic import generate

ROWS = 800
REPLAY_SEED = 2026
LABEL_SEED = 77
COPY_RATE = 0.70
ESCALATION_LOW = 0.40
ESCALATION_HIGH = 0.60


def evaluate_replay(models) -> dict:
    """Compare fixed model outputs under two label sources on identical cases."""
    cohorts = []
    for name, shifted in (("Reference-like", False), ("Shifted inputs", True)):
        panel, reference = generate(ROWS, REPLAY_SEED, shifted)
        first_score = models["v1"].predict_proba(panel)[:, 1]
        second_score = models["v2"].predict_proba(panel)[:, 1]
        first = first_score >= REVIEW_THRESHOLD
        second = second_score >= REVIEW_THRESHOLD

        # Copy the baseline suggestion on a seeded subset. The independent
        # simulator label remains unchanged and is never an input to scoring.
        copied = np.random.default_rng(LABEL_SEED).random(ROWS) < COPY_RATE
        assisted = np.where(copied, first, reference)
        escalate = (first_score >= ESCALATION_LOW) & (first_score < ESCALATION_HIGH)
        cascade = np.where(escalate, second, first)
        cohorts.append({
            "name": name,
            "rows": ROWS,
            "copied_labels": int(copied.sum()),
            "escalated": int(escalate.sum()),
            "agreement": [
                {
                    "policy": policy,
                    "independent_reference": float(np.mean(predicted == reference)),
                    "model_influenced": float(np.mean(predicted == assisted)),
                }
                for policy, predicted in
                (("v1 only", first), ("v2 only", second), ("Two-stage cascade", cascade))
            ],
        })
    return {
        "source": "synthetic-offline-replay",
        "replay_seed": REPLAY_SEED,
        "label_seed": LABEL_SEED,
        "classification_threshold": REVIEW_THRESHOLD,
        "escalation_band": [ESCALATION_LOW, ESCALATION_HIGH],
        "cohorts": cohorts,
    }
