import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS face_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    is_augmented INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cameras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    stream_url TEXT NOT NULL,
    location TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_frame TEXT,
    source_type TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name TEXT NOT NULL,
    camera_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    snapshot_path TEXT DEFAULT '',
    clip_path TEXT DEFAULT '',
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_false_positive INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS augmented_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER,
    source_filename TEXT NOT NULL,
    output_filename TEXT NOT NULL,
    output_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);
"""


def get_db():
    if "db" not in g:
        db_path = Path(current_app.instance_path) / current_app.config["DATABASE"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _ensure_column(db, table, column, coltype):
    existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    # CREATE TABLE IF NOT EXISTS doesn't retrofit columns onto a db file that
    # predates a schema change, so patch older databases up explicitly.
    _ensure_column(db, "detections", "clip_path", "TEXT DEFAULT ''")
    _ensure_column(db, "cameras", "last_frame", "TEXT")
    _ensure_column(db, "cameras", "source_type", "TEXT NOT NULL DEFAULT 'manual'")
    _ensure_column(db, "augmented_images", "person_id", "INTEGER REFERENCES people(id) ON DELETE CASCADE")
    db.commit()
