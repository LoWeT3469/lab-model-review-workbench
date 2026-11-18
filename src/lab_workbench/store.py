"""SQLite storage with write transactions for the local demo."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def decode_row(row, json_columns=()):
    result = dict(row)
    for name in json_columns:
        result[name] = json.loads(result[name])
    return result


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS predictions (
                    request_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    model_sha256 TEXT NOT NULL,
                    panel TEXT NOT NULL,
                    score REAL NOT NULL,
                    suggested_review INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL REFERENCES predictions(request_id),
                    created_at TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    note TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS reviews_case ON reviews(request_id);
                CREATE TABLE IF NOT EXISTS model_events (
                    event_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    previous_version TEXT,
                    version TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    request_id TEXT,
                    status INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    measurable INTEGER NOT NULL,
                    missing TEXT NOT NULL,
                    outcome TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS attempts_time ON attempts(created_at);
                CREATE INDEX IF NOT EXISTS predictions_time ON predictions(created_at);
            """)

    @contextmanager
    def connect(self, write: bool = False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                if write:
                    db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def active_version(self, db) -> str:
        return db.execute(
            "SELECT version FROM model_events ORDER BY event_id DESC LIMIT 1"
        ).fetchone()["version"]

    def record_attempt(self, created_at, request_id, status, latency_ms, measurable, missing, outcome):
        with self.connect(write=True) as db:
            db.execute(
                """INSERT INTO attempts
                   (created_at, request_id, status, latency_ms, measurable, missing, outcome)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (created_at, request_id, status, latency_ms, measurable, encode(missing), outcome),
            )
