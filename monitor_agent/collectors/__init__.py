"""Activity collectors.

Each collector is a small, self-contained unit with a uniform interface used by
the scheduler:

- Polling collectors expose ``collect_once()`` (screenshots, browser URLs).
- Streaming collectors expose ``start()`` / ``stop()`` and flush on their own
  cadence (keystroke activity counting).
"""

from .browser_urls import BrowserUrlCollector
from .keystrokes import KeystrokeActivityCollector
from .screenshots import ScreenshotCollector

__all__ = [
    "BrowserUrlCollector",
    "KeystrokeActivityCollector",
    "ScreenshotCollector",
]
