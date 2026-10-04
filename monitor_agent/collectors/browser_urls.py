"""Browser URL collector.

Reads visited URLs from each browser's OWN history database. It does not
intercept traffic or inject into the browser; it reads the same history the user
can see. The history file is copied before reading because browsers keep it
locked while running.

Supported: Chromium-family (Chrome, Edge) and Firefox. Paths are the standard
Windows profile locations.
"""
from __future__ import annotations

import glob
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from ..config import BrowserConfig
from ..storage import Storage

log = logging.getLogger(__name__)

# Seconds between the Windows FILETIME epoch (1601-01-01) and Unix epoch.
_CHROME_EPOCH_OFFSET = 11644473600


def _local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")))


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", os.path.expanduser("~")))


def _chromium_history_paths(vendor_rel: str) -> list[Path]:
    """Return History DB paths for all profiles of a Chromium-based browser."""
    base = _local_appdata() / vendor_rel / "User Data"
    if not base.exists():
        return []
    paths = []
    for profile in ["Default", *glob.glob(str(base / "Profile *"))]:
        p = base / profile / "History" if profile == "Default" else Path(profile) / "History"
        if p.exists():
            paths.append(p)
    return paths


def _firefox_history_paths() -> list[Path]:
    base = _appdata() / "Mozilla" / "Firefox" / "Profiles"
    if not base.exists():
        return []
    return [Path(p) for p in glob.glob(str(base / "*" / "places.sqlite"))]


# browser name -> (list of history db paths, converter query)
_BROWSERS = {
    "chrome": lambda: _chromium_history_paths("Google/Chrome"),
    "edge": lambda: _chromium_history_paths("Microsoft/Edge"),
    "firefox": _firefox_history_paths,
}


class BrowserUrlCollector:
    def __init__(self, config: BrowserConfig, storage: Storage):
        self.config = config
        self.storage = storage

    @property
    def interval(self) -> int:
        return max(1, int(self.config.poll_seconds))

    def collect_once(self) -> int:
        total = 0
        for browser in self.config.browsers:
            finder = _BROWSERS.get(browser.lower())
            if finder is None:
                log.warning("Unknown browser %r; skipping", browser)
                continue
            for db_path in finder():
                try:
                    rows = self._read_db(browser.lower(), db_path)
                    total += self.storage.add_browser_urls(browser.lower(), rows)
                except Exception as exc:  # noqa: BLE001
                    log.error("Reading %s history at %s failed: %s", browser, db_path, exc)
        if total:
            log.debug("Recorded %d new browser URL(s)", total)
        return total

    def _read_db(self, browser: str, db_path: Path) -> list[tuple[str, str, float]]:
        # Copy because the live DB is locked by the running browser.
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / "history.db"
            shutil.copy2(db_path, copy_path)
            conn = sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True)
            try:
                conn.row_factory = sqlite3.Row
                if browser == "firefox":
                    return self._read_firefox(conn)
                return self._read_chromium(conn)
            finally:
                conn.close()

    @staticmethod
    def _read_chromium(conn: sqlite3.Connection) -> list[tuple[str, str, float]]:
        cur = conn.execute(
            "SELECT url, title, last_visit_time FROM urls "
            "ORDER BY last_visit_time DESC LIMIT 2000"
        )
        out = []
        for r in cur.fetchall():
            lvt = r["last_visit_time"] or 0
            # Chromium stores microseconds since 1601-01-01.
            visit = (lvt / 1_000_000) - _CHROME_EPOCH_OFFSET if lvt else 0.0
            out.append((r["url"], r["title"] or "", float(visit)))
        return out

    @staticmethod
    def _read_firefox(conn: sqlite3.Connection) -> list[tuple[str, str, float]]:
        cur = conn.execute(
            "SELECT url, title, last_visit_date FROM moz_places "
            "WHERE last_visit_date IS NOT NULL "
            "ORDER BY last_visit_date DESC LIMIT 2000"
        )
        out = []
        for r in cur.fetchall():
            lvd = r["last_visit_date"] or 0
            # Firefox stores microseconds since the Unix epoch.
            visit = lvd / 1_000_000 if lvd else 0.0
            out.append((r["url"], r["title"] or "", float(visit)))
        return out
