"""Tests for the keystroke ACTIVITY collector.

The central guarantee under test: only counts are produced, never key identity.
We exercise the callback and flush logic directly, without starting a real
global listener (which needs a display/privileges).
"""
from monitor_agent.collectors.keystrokes import KeystrokeActivityCollector
from monitor_agent.config import KeystrokeConfig
from monitor_agent.storage import Storage


def test_on_press_counts_and_ignores_key(tmp_path):
    s = Storage(tmp_path / "m.db")
    col = KeystrokeActivityCollector(KeystrokeConfig(window_seconds=60), s)

    # Simulate presses of different "keys" — the argument must be ignored.
    for key in ["a", "b", "secret-password-char", object()]:
        col._on_press(key)

    assert col._count == 4
    s.close()


def test_flush_writes_only_count(tmp_path):
    s = Storage(tmp_path / "m.db")
    col = KeystrokeActivityCollector(KeystrokeConfig(window_seconds=60), s)
    col._on_press("x")
    col._on_press("y")
    col._flush()

    row = s._conn.execute(
        "SELECT window_start, window_end, count FROM keystroke_counts"
    ).fetchone()
    assert row["count"] == 2
    assert row["window_end"] >= row["window_start"]
    # Counter resets after flush.
    assert col._count == 0
    s.close()
