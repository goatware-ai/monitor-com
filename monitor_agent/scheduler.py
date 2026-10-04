"""Orchestration.

Runs the enabled collectors: polling collectors on their own interval threads,
the keystroke activity collector as a streaming listener, and a periodic
retention purge. Designed to shut down cleanly on stop().
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from .collectors import (
    BrowserUrlCollector,
    KeystrokeActivityCollector,
    ScreenshotCollector,
)
from .config import Config
from .storage import Storage

log = logging.getLogger(__name__)


class _PollWorker(threading.Thread):
    """Calls collector.collect_once() every `interval` seconds until stopped."""

    def __init__(self, name: str, collector, interval: int, stop_event: threading.Event):
        super().__init__(name=name, daemon=True)
        self._collector = collector
        self._interval = max(1, interval)
        self._stop = stop_event

    def run(self) -> None:
        # Do an immediate first collection, then loop on the interval.
        while not self._stop.is_set():
            try:
                self._collector.collect_once()
            except Exception as exc:  # noqa: BLE001
                log.error("%s collection error: %s", self.name, exc)
            self._stop.wait(timeout=self._interval)


class Agent:
    """Top-level agent: owns storage, collectors and lifecycle."""

    def __init__(self, config: Config):
        self.config = config
        self.storage = Storage(config.storage.database_path)
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []
        self._keystrokes: KeystrokeActivityCollector | None = None
        self._root = config.storage.root_path

    def start(self) -> None:
        cfg = self.config
        if cfg.screenshots.enabled:
            col = ScreenshotCollector(cfg.screenshots, self.storage, self._root)
            self._workers.append(
                _PollWorker("screenshots", col, col.interval, self._stop)
            )
        if cfg.browser.enabled:
            col = BrowserUrlCollector(cfg.browser, self.storage)
            self._workers.append(
                _PollWorker("browser-urls", col, col.interval, self._stop)
            )
        if cfg.keystrokes.enabled:
            self._keystrokes = KeystrokeActivityCollector(cfg.keystrokes, self.storage)
            self._keystrokes.start()

        if cfg.retention.days > 0:
            self._workers.append(
                _PollWorker(
                    "retention",
                    _RetentionTask(self.storage, cfg.retention.days),
                    max(1, cfg.retention.purge_check_hours) * 3600,
                    self._stop,
                )
            )

        for w in self._workers:
            w.start()
        enabled = [
            name
            for name, on in [
                ("screenshots", cfg.screenshots.enabled),
                ("browser-urls", cfg.browser.enabled),
                ("keystroke-activity", cfg.keystrokes.enabled),
            ]
            if on
        ]
        log.info("Agent started. Active collectors: %s", ", ".join(enabled) or "none")

    def run_forever(self) -> None:
        self.start()
        try:
            while not self._stop.is_set():
                self._stop.wait(timeout=1.0)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        if self._stop.is_set():
            return
        log.info("Stopping agent...")
        self._stop.set()
        if self._keystrokes is not None:
            self._keystrokes.stop()
        for w in self._workers:
            w.join(timeout=5.0)
        self.storage.close()
        log.info("Agent stopped.")


class _RetentionTask:
    """Adapter so the purge runs on a _PollWorker like a collector."""

    def __init__(self, storage: Storage, days: int):
        self.storage = storage
        self.days = days

    def collect_once(self) -> None:
        cutoff = time.time() - self.days * 86400
        removed = self.storage.purge_older_than(cutoff)
        for path in removed:
            try:
                os.remove(path)
            except OSError:
                pass
        if removed:
            log.info("Retention purge removed %d screenshot file(s)", len(removed))
