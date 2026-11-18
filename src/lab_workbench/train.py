"""Train two immutable release artifacts in one manifest directory."""

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .schema import FEATURES
from .synthetic import generate

SEED = 42


def train(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"{destination} already exists. Choose a new model directory.")
    panel, labels = generate(2400, SEED)
    x_train, x_test, y_train, y_test = train_test_split(
        panel, labels, test_size=0.25, random_state=SEED, stratify=labels
    )
    estimators = {
        "v1": ("Logistic regression", LogisticRegression(random_state=SEED)),
        "v2": ("Random forest", RandomForestClassifier(
            n_estimators=100, max_depth=7, min_samples_leaf=12, random_state=SEED
        )),
    }
    manifest = {
        "source": "synthetic-panel-v1",
        "seed": SEED,
        "features": list(FEATURES),
        "scikit_learn": sklearn.__version__,
        "train_rows": len(x_train),
        "holdout_rows": len(x_test),
        "versions": {},
        "reference": {},
    }
    for name in FEATURES:
        values = x_train[name].dropna()
        edges = np.quantile(values, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist()
        counts = np.histogram(values, bins=[-np.inf, *edges, np.inf])[0]
        manifest["reference"][name] = {
            "edges": edges,
            "fractions": (counts / counts.sum()).tolist(),
        }

    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        release = Path(staging) / "release"
        release.mkdir()
        for version, (name, estimator) in estimators.items():
            model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), estimator)
            model.fit(x_train, y_train)
            scores = model.predict_proba(x_test)[:, 1]
            artifact = release / f"{version}.joblib"
            joblib.dump(model, artifact)
            manifest["versions"][version] = {
                "name": name,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "roc_auc": round(roc_auc_score(y_test, scores), 4),
                "average_precision": round(average_precision_score(y_test, scores), 4),
            }
        (release / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(release, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/models"))
    args = parser.parse_args()
    train(args.output)


if __name__ == "__main__":
    main()
