"""Keystroke ACTIVITY collector.

Counts key-press events and records only a **count** per time window
(default one minute). This measures how actively someone is typing without ever
capturing what they type.

Privacy guarantee (by design):
  * The ``on_press`` callback takes NO argument carrying the key and only
    increments an integer counter.
  * The key's identity is never read, stored, logged, or transmitted.
  * This is NOT a keylogger and must not be modified into one
    (see docs/ACCEPTABLE_USE.md).
"""
from __future__ import annotations

import logging
import threading
import time

from ..config import KeystrokeConfig
from ..storage import Storage

log = logging.getLogger(__name__)


class KeystrokeActivityCollector:
    def __init__(self, config: KeystrokeConfig, storage: Storage):
        self.config = config
        self.storage = storage
        self._count = 0
        self._count_lock = threading.Lock()
        self._window_start = time.time()
        self._listener = None
        self._flush_thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def window_seconds(self) -> int:
        return max(1, int(self.config.window_seconds))

    # -- listener callback -------------------------------------------------
    def _on_press(self, _key) -> None:
        """Increment the counter. The key argument is intentionally ignored so
        that no information about which key was pressed is ever retained."""
        with self._count_lock:
            self._count += 1

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        try:
            from pynput import keyboard
        except Exception as exc:  # noqa: BLE001
            log.error("Keystroke counting unavailable (pynput import failed): %s", exc)
            return

        self._window_start = time.time()
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, name="keystroke-flush", daemon=True
        )
        self._flush_thread.start()
        log.info(
            "Keystroke ACTIVITY counting started (counts only, %ds windows).",
            self.window_seconds,
        )

    def _flush_loop(self) -> None:
        while not self._stop.is_set():
            # Sleep in small steps so stop() is responsive.
            self._stop.wait(timeout=self.window_seconds)
            self._flush()

    def _flush(self) -> None:
        now = time.time()
        with self._count_lock:
            count = self._count
            self._count = 0
            start = self._window_start
            self._window_start = now
        # Record every window, including zero-activity windows, so the timeline
        # is complete.
        try:
            self.storage.add_keystroke_count(start, now, count)
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to store keystroke count: %s", exc)

    def stop(self) -> None:
        self._stop.set()
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:  # noqa: BLE001
                pass
        # Flush whatever is pending in the final window.
        self._flush()
        log.info("Keystroke activity counting stopped.")
