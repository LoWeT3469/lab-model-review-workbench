"""Local FastAPI service. The app factory supports isolated tests."""

import hashlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import UUID

import joblib
import pandas as pd
import sklearn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .monitor import snapshot
from .schema import Activation, FEATURES, PredictionRequest, Review
from .store import Store, decode_row, encode, utc_now

logger = logging.getLogger(__name__)


def load_release(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["features"] != list(FEATURES) or manifest["scikit_learn"] != sklearn.__version__:
        raise RuntimeError("Model manifest is incompatible with this service")
    models = {}
    for version, entry in manifest["versions"].items():
        artifact = (directory / f"{version}.joblib").read_bytes()
        if hashlib.sha256(artifact).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Checksum mismatch for model {version}")
        models[version] = joblib.load(BytesIO(artifact))
    return manifest, models


def describe_attempt(request, body):
    if not isinstance(body, dict):
        return
    try:
        request.state.request_id = str(UUID(str(body.get("request_id"))))
    except ValueError:
        pass
    panel = body.get("panel")
    if isinstance(panel, dict):
        request.state.missing = [name for name in FEATURES if panel.get(name) is None]


def create_app(model_dir: Path | None = None, database: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        manifest, models = load_release(model_dir or Path(os.getenv("MODEL_DIR", "artifacts/models")))
        store = Store(database or Path(os.getenv("WORKBENCH_DB", "data/workbench.sqlite3")))
        with store.connect(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS model_bindings (
                version TEXT PRIMARY KEY, sha256 TEXT NOT NULL
            )""")
            for version, entry in manifest["versions"].items():
                db.execute("INSERT OR IGNORE INTO model_bindings VALUES (?, ?)",
                           (version, entry["sha256"]))
            bindings = {row["version"]: row["sha256"] for row in db.execute("SELECT * FROM model_bindings")}
            if bindings != {v: m["sha256"] for v, m in manifest["versions"].items()}:
                raise RuntimeError("Database belongs to a different model release")
            if not db.execute("SELECT 1 FROM model_events LIMIT 1").fetchone():
                db.execute(
                    "INSERT INTO model_events (created_at, version, reason) VALUES (?, ?, ?)",
                    (utc_now(), "v1", "Initial demo release"),
                )
        app.state.store, app.state.manifest, app.state.models = store, manifest, models
        yield

    app = FastAPI(title="Lab Model Review Workbench", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if request.url.path == "/predictions" and request.method == "POST":
            describe_attempt(request, exc.body)
        detail = [{k: error[k] for k in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.middleware("http")
    async def observe_predictions(request: Request, call_next):
        if request.method != "POST" or request.url.path != "/predictions":
            return await call_next(request)
        start, created_at = time.perf_counter(), utc_now()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Prediction failed")
            response = JSONResponse(status_code=500, content={"detail": "Prediction service failed"})
        missing = getattr(request.state, "missing", None)
        try:
            await run_in_threadpool(
                app.state.store.record_attempt,
                created_at, getattr(request.state, "request_id", None), response.status_code,
                (time.perf_counter() - start) * 1000, missing is not None, missing or [],
                getattr(request.state, "outcome", "rejected" if response.status_code < 500 else "error"),
            )
        except Exception:
            logger.exception("Could not persist prediction telemetry")
        return response

    @app.get("/health")
    def health():
        with app.state.store.connect() as db:
            return {"status": "ready", "active_version": app.state.store.active_version(db)}

    @app.post("/predictions")
    def predict(body: PredictionRequest, request: Request):
        describe_attempt(request, body.model_dump(mode="json"))
        request_id = str(body.request_id)
        panel = body.panel.model_dump()
        canonical = encode(panel)
        store = app.state.store
        with store.connect(write=True) as db:
            existing = db.execute(
                "SELECT * FROM predictions WHERE request_id = ?", (request_id,)
            ).fetchone()
            if existing:
                if existing["panel"] != canonical:
                    raise HTTPException(409, "This request ID already belongs to a different panel")
                request.state.outcome = "replayed"
                return {**decode_row(existing, ("panel",)), "replayed": True}

            version = store.active_version(db)
            frame = pd.DataFrame([panel], columns=list(FEATURES), dtype=float)
            score = float(app.state.models[version].predict_proba(frame)[0, 1])
            record = {
                "request_id": request_id,
                "created_at": utc_now(),
                "model_version": version,
                "model_sha256": app.state.manifest["versions"][version]["sha256"],
                "panel": canonical,
                "score": score,
                "suggested_review": int(score >= 0.5),
            }
            db.execute(
                """INSERT INTO predictions VALUES
                   (:request_id, :created_at, :model_version, :model_sha256, :panel,
                    :score, :suggested_review)""", record,
            )
        request.state.outcome = "created"
        return {**record, "panel": panel, "replayed": False}

    @app.get("/predictions")
    def list_predictions(limit: int = Query(default=40, ge=1, le=100)):
        with app.state.store.connect() as db:
            rows = db.execute("""
                SELECT p.*, (SELECT disposition FROM reviews r WHERE r.request_id = p.request_id
                    ORDER BY r.rowid DESC LIMIT 1) AS latest_review
                FROM predictions p ORDER BY p.rowid DESC LIMIT ?
            """, (limit,)).fetchall()
        return [decode_row(row, ("panel",)) for row in rows]

    @app.get("/predictions/{request_id}")
    def case(request_id: UUID):
        with app.state.store.connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT * FROM predictions WHERE request_id = ?", (str(request_id),)).fetchone()
            if not row:
                raise HTTPException(404, "Prediction not found")
            reviews = db.execute(
                "SELECT * FROM reviews WHERE request_id = ? ORDER BY rowid",
                (str(request_id),),
            ).fetchall()
        return {**decode_row(row, ("panel",)), "reviews": [dict(review) for review in reviews]}

    @app.post("/predictions/{request_id}/reviews")
    def review(request_id: UUID, body: Review):
        payload = {"request_id": str(request_id), **body.model_dump(mode="json")}
        with app.state.store.connect(write=True) as db:
            if not db.execute("SELECT 1 FROM predictions WHERE request_id = ?", (str(request_id),)).fetchone():
                raise HTTPException(404, "Prediction not found")
            existing = db.execute("SELECT * FROM reviews WHERE review_id = ?", (str(body.review_id),)).fetchone()
            if existing:
                if any(existing[key] != value for key, value in payload.items()):
                    raise HTTPException(409, "This review ID already belongs to different feedback")
                return {**dict(existing), "replayed": True}
            record = {**payload, "created_at": utc_now()}
            db.execute(
                """INSERT INTO reviews VALUES
                   (:review_id, :request_id, :created_at, :reviewer, :disposition, :note)""", record,
            )
        return {**record, "replayed": False}

    @app.get("/models")
    def models():
        with app.state.store.connect() as db:
            db.execute("BEGIN")
            active = app.state.store.active_version(db)
            history = db.execute("SELECT * FROM model_events ORDER BY event_id DESC LIMIT 25").fetchall()
        return {
            "active_version": active,
            "releases": app.state.manifest["versions"],
            "source": app.state.manifest["source"],
            "seed": app.state.manifest["seed"],
            "holdout_rows": app.state.manifest["holdout_rows"],
            "history": [dict(row) for row in history],
        }

    @app.post("/models/activate")
    def activate(body: Activation):
        if body.version not in app.state.models:
            raise HTTPException(404, "Unknown model version")
        store = app.state.store
        with store.connect(write=True) as db:
            previous = store.active_version(db)
            if previous != body.version:
                db.execute("""
                    INSERT INTO model_events (created_at, previous_version, version, reason)
                    VALUES (?, ?, ?, ?)
                """, (utc_now(), previous, body.version, body.reason))
        return {"active_version": body.version, "changed": previous != body.version}

    @app.get("/monitor")
    def monitor(hours: int = Query(default=24, ge=1, le=168)):
        return snapshot(app.state.store, app.state.manifest["reference"], hours)

    return app


app = create_app()
