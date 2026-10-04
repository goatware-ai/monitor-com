"""Tests for browser history time conversion, using in-memory SQLite DBs that
mimic the real Chromium `urls` and Firefox `moz_places` schemas."""
import sqlite3

from monitor_agent.collectors.browser_urls import (
    _CHROME_EPOCH_OFFSET,
    BrowserUrlCollector,
)


def test_chromium_time_conversion():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE urls (url TEXT, title TEXT, last_visit_time INTEGER)")
    # Unix time 1_700_000_000 -> chromium microseconds since 1601.
    chromium_us = int((1_700_000_000 + _CHROME_EPOCH_OFFSET) * 1_000_000)
    conn.execute(
        "INSERT INTO urls VALUES (?, ?, ?)",
        ("https://example.test", "Example", chromium_us),
    )
    rows = BrowserUrlCollector._read_chromium(conn)
    assert rows[0][0] == "https://example.test"
    assert rows[0][1] == "Example"
    assert abs(rows[0][2] - 1_700_000_000) < 1.0


def test_firefox_time_conversion():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE moz_places (url TEXT, title TEXT, last_visit_date INTEGER)")
    firefox_us = 1_700_000_000 * 1_000_000  # microseconds since unix epoch
    conn.execute(
        "INSERT INTO moz_places VALUES (?, ?, ?)",
        ("https://firefox.test", "FF", firefox_us),
    )
    rows = BrowserUrlCollector._read_firefox(conn)
    assert rows[0][0] == "https://firefox.test"
    assert abs(rows[0][2] - 1_700_000_000) < 1.0
