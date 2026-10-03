"""Storage: SQLite locally, Postgres (e.g. Supabase) when DATABASE_URL is a postgres:// URL.

One row per vendor holds both the bot state and the listing, as in the plan
("the bot is a small state machine stored on Noor's row").
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vendors (
  id {pk},
  phone TEXT UNIQUE NOT NULL,
  state TEXT NOT NULL DEFAULT 'NEW',
  consented INTEGER NOT NULL DEFAULT 0,
  photo_path TEXT,
  audio_path TEXT,
  typed_text TEXT,
  transcript TEXT,
  transcript_en TEXT,
  asr_confidence REAL,
  review_reasons TEXT,
  draft_json TEXT,
  listing_json TEXT,
  readback_text TEXT,
  readback_audio TEXT,
  pending_lat REAL,
  pending_lon REAL,
  lat REAL,
  lon REAL,
  privacy TEXT,
  live INTEGER NOT NULL DEFAULT 0,
  hidden INTEGER NOT NULL DEFAULT 0,
  verified INTEGER NOT NULL DEFAULT 0,
  seed INTEGER NOT NULL DEFAULT 0,
  met_count INTEGER NOT NULL DEFAULT 0,
  report_count INTEGER NOT NULL DEFAULT 0,
  interest_count INTEGER NOT NULL DEFAULT 0,
  last_checkin TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pipeline_metrics (
  id {pk},
  vendor_id INTEGER,
  stage TEXT NOT NULL,
  seconds REAL NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS web_outbox (
  id {pk},
  phone TEXT NOT NULL,
  text TEXT,
  media_url TEXT,
  created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, url: str):
        self.url = url
        self.is_pg = url.startswith(("postgres://", "postgresql://"))
        self._lock = threading.Lock()
        if not self.is_pg:
            self._path = url.removeprefix("sqlite:///")
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        if self.is_pg:
            import psycopg  # only needed for Postgres
            from psycopg.rows import dict_row

            return psycopg.connect(self.url, row_factory=dict_row)
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        pk = "BIGSERIAL PRIMARY KEY" if self.is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        with self._lock, self._connect() as conn:
            for stmt in _SCHEMA.format(pk=pk).split(";"):
                if stmt.strip():
                    conn.execute(stmt)

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql.replace("?", "%s") if self.is_pg else sql, params)
            return [dict(r) for r in cur.fetchall()] if cur.description else []

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None


db = DB(settings.database_url)


# --- Vendors -----------------------------------------------------------------------

def get_or_create_vendor(phone: str) -> dict[str, Any]:
    row = db.one("SELECT * FROM vendors WHERE phone = ?", (phone,))
    if row:
        return row
    ts = now()
    return db.one("INSERT INTO vendors (phone, created_at, updated_at) VALUES (?, ?, ?) RETURNING *", (phone, ts, ts))


def get_vendor(vendor_id: int) -> dict[str, Any] | None:
    return db.one("SELECT * FROM vendors WHERE id = ?", (vendor_id,))


def update_vendor(vendor_id: int, **fields: Any) -> dict[str, Any]:
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    return db.one(f"UPDATE vendors SET {cols} WHERE id = ? RETURNING *", (*fields.values(), vendor_id))


def live_listings() -> list[dict[str, Any]]:
    return db.query("SELECT * FROM vendors WHERE live = 1 AND hidden = 0 AND lat IS NOT NULL ORDER BY updated_at DESC")


def increment(vendor_id: int, column: str) -> dict[str, Any] | None:
    assert column in {"met_count", "report_count", "interest_count"}
    return db.one(f"UPDATE vendors SET {column} = {column} + 1 WHERE id = ? RETURNING *", (vendor_id,))


def listing_of(row: dict[str, Any]) -> dict[str, Any] | None:
    return json.loads(row["listing_json"]) if row.get("listing_json") else None


# --- Metrics -------------------------------------------------------------------------

def add_metric(vendor_id: int | None, stage: str, seconds: float, detail: str = "") -> None:
    db.query(
        "INSERT INTO pipeline_metrics (vendor_id, stage, seconds, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (vendor_id, stage, round(seconds, 3), detail, now()),
    )


def metric_summary() -> list[dict[str, Any]]:
    return db.query(
        "SELECT stage, COUNT(*) AS runs, AVG(seconds) AS avg_seconds, MAX(seconds) AS max_seconds "
        "FROM pipeline_metrics GROUP BY stage ORDER BY stage"
    )


# --- Web channel outbox (the /host page polls this) --------------------------------

def add_web_message(phone: str, text: str | None, media_url: str | None) -> None:
    db.query("INSERT INTO web_outbox (phone, text, media_url, created_at) VALUES (?, ?, ?, ?)", (phone, text, media_url, now()))


def web_messages(phone: str, after_id: int = 0) -> list[dict[str, Any]]:
    return db.query("SELECT * FROM web_outbox WHERE phone = ? AND id > ? ORDER BY id", (phone, after_id))
