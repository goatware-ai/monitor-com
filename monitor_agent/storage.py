"""Local SQLite storage for collected metadata.

Screenshots are written as image files to disk; this database stores their
metadata plus browser URLs, keystroke activity counts, and the consent record.
Everything stays local to the machine unless the operator builds and configures
their own export.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consent (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    acknowledged  INTEGER NOT NULL,
    notice        TEXT,
    acknowledged_at REAL
);

CREATE TABLE IF NOT EXISTS screenshots (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    path      TEXT NOT NULL,
    monitor   INTEGER,
    width     INTEGER,
    height    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_screenshots_ts ON screenshots(ts);

CREATE TABLE IF NOT EXISTS browser_urls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    browser     TEXT NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT,
    visit_time  REAL,
    UNIQUE(browser, url, visit_time)
);
CREATE INDEX IF NOT EXISTS idx_browser_urls_ts ON browser_urls(ts);

-- Keystroke ACTIVITY: we store only the count per window. The identity of the
-- keys pressed is never captured or stored.
CREATE TABLE IF NOT EXISTS keystroke_counts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    window_start  REAL NOT NULL,
    window_end    REAL NOT NULL,
    count         INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_keystroke_window ON keystroke_counts(window_start);
"""


class Storage:
    """Thread-safe wrapper around a single SQLite database."""

    def __init__(self, db_path: Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False because collectors run on worker threads; all
        # access is serialized through self._lock.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # --- consent ---------------------------------------------------------
    def get_consent(self) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM consent WHERE id = 1")
            return cur.fetchone()

    def record_consent(self, notice: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO consent (id, acknowledged, notice, acknowledged_at) "
                "VALUES (1, 1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET acknowledged=1, notice=excluded.notice, "
                "acknowledged_at=excluded.acknowledged_at",
                (notice, time.time()),
            )
            self._conn.commit()

    # --- screenshots -----------------------------------------------------
    def add_screenshot(self, path: str, monitor: int, width: int, height: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO screenshots (ts, path, monitor, width, height) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), path, monitor, width, height),
            )
            self._conn.commit()

    # --- browser urls ----------------------------------------------------
    def add_browser_urls(self, browser: str, rows: list[tuple[str, str, float]]) -> int:
        """rows: list of (url, title, visit_time_epoch). Returns # inserted."""
        inserted = 0
        now = time.time()
        with self._lock:
            for url, title, visit_time in rows:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO browser_urls "
                    "(ts, browser, url, title, visit_time) VALUES (?, ?, ?, ?, ?)",
                    (now, browser, url, title, visit_time),
                )
                inserted += cur.rowcount
            self._conn.commit()
        return inserted

    # --- keystroke counts ------------------------------------------------
    def add_keystroke_count(self, window_start: float, window_end: float, count: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO keystroke_counts (window_start, window_end, count) "
                "VALUES (?, ?, ?)",
                (window_start, window_end, count),
            )
            self._conn.commit()

    # --- retention -------------------------------------------------------
    def purge_older_than(self, cutoff_epoch: float) -> list[str]:
        """Delete rows older than cutoff. Returns screenshot file paths that
        should be removed from disk by the caller."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT path FROM screenshots WHERE ts < ?", (cutoff_epoch,)
            )
            paths = [r["path"] for r in cur.fetchall()]
            self._conn.execute("DELETE FROM screenshots WHERE ts < ?", (cutoff_epoch,))
            self._conn.execute("DELETE FROM browser_urls WHERE ts < ?", (cutoff_epoch,))
            self._conn.execute(
                "DELETE FROM keystroke_counts WHERE window_start < ?", (cutoff_epoch,)
            )
            self._conn.commit()
        return paths

    def close(self) -> None:
        with self._lock:
            self._conn.close()
