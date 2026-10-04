import time

from monitor_agent.storage import Storage


def _storage(tmp_path):
    return Storage(tmp_path / "monitor.db")


def test_consent_roundtrip(tmp_path):
    s = _storage(tmp_path)
    assert s.get_consent() is None
    s.record_consent("notice text")
    row = s.get_consent()
    assert row["acknowledged"] == 1
    assert row["notice"] == "notice text"
    assert row["acknowledged_at"] > 0
    s.close()


def test_browser_url_dedup(tmp_path):
    s = _storage(tmp_path)
    rows = [("https://a.test", "A", 100.0), ("https://b.test", "B", 200.0)]
    assert s.add_browser_urls("chrome", rows) == 2
    # Same rows again -> deduped by UNIQUE(browser, url, visit_time).
    assert s.add_browser_urls("chrome", rows) == 0
    s.close()


def test_keystroke_counts_store_only_counts(tmp_path):
    s = _storage(tmp_path)
    s.add_keystroke_count(1000.0, 1060.0, 73)
    cur = s._conn.execute("SELECT window_start, window_end, count FROM keystroke_counts")
    row = cur.fetchone()
    assert row["count"] == 73
    # Schema has no column that could hold key identity.
    cols = {d[1] for d in s._conn.execute("PRAGMA table_info(keystroke_counts)")}
    assert cols == {"id", "window_start", "window_end", "count"}
    s.close()


def test_retention_purge(tmp_path):
    s = _storage(tmp_path)
    old = time.time() - 10_000
    f = tmp_path / "old.png"
    f.write_bytes(b"x")
    s.add_screenshot(str(f), 1, 10, 10)
    # Backdate the row.
    s._conn.execute("UPDATE screenshots SET ts = ?", (old,))
    s._conn.commit()
    removed = s.purge_older_than(time.time() - 100)
    assert str(f) in removed
    assert s._conn.execute("SELECT COUNT(*) c FROM screenshots").fetchone()["c"] == 0
    s.close()
