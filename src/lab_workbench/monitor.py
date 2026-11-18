"""Operational telemetry and unlabeled input distribution monitoring."""

from datetime import datetime, timedelta, timezone
import json

import numpy as np

from .schema import FEATURES

MIN_OBSERVATIONS = 20
SHIFT_THRESHOLD = 0.20


def snapshot(store, reference, hours: int) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="milliseconds")
    with store.connect() as db:
        db.execute("BEGIN")
        attempts = db.execute(
            "SELECT * FROM attempts WHERE created_at >= ?", (since,)
        ).fetchall()
        predictions = db.execute(
            "SELECT panel FROM predictions WHERE created_at >= ?", (since,)
        ).fetchall()

    count = len(attempts)
    measured = [json.loads(row["missing"]) for row in attempts if row["measurable"]]
    failure_count = sum(row["status"] >= 400 for row in attempts)
    panels = [json.loads(row["panel"]) for row in predictions]
    drift = {}
    for name, baseline in reference.items():
        values = [panel[name] for panel in panels if panel[name] is not None]
        edges = [-np.inf, *baseline["edges"], np.inf]
        live = (np.histogram(values, bins=edges)[0] / len(values)).tolist() if values else None
        distance = None
        if len(values) >= MIN_OBSERVATIONS:
            distance = float(np.abs(np.array(live) - baseline["fractions"]).sum() / 2)
        drift[name] = {
            "n": len(values),
            "edges": baseline["edges"],
            "reference_fractions": baseline["fractions"],
            "live_fractions": live,
            "distance": distance,
            "status": ("insufficient data" if distance is None else
                       "shift signal" if distance >= SHIFT_THRESHOLD else "below demo threshold"),
        }
    return {
        "window_hours": hours,
        "attempts": count,
        "unique_predictions": len(predictions),
        "deduplicated": sum(row["outcome"] == "replayed" for row in attempts),
        "validation_failures": sum(row["status"] == 422 for row in attempts),
        "service_errors": sum(row["status"] >= 500 for row in attempts),
        "failure_rate": failure_count / count if count else None,
        "p95_ms": float(np.percentile([row["latency_ms"] for row in attempts], 95)) if count else None,
        "missingness_denominator": len(measured),
        "missing_rates": {
            name: sum(name in missing for missing in measured) / len(measured) if measured else None
            for name in FEATURES
        },
        "drift": drift,
    }
