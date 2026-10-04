"""System tray presence.

A visible tray icon is a core transparency feature: the monitored user can
always see the agent is running and open a "What is monitored" screen. This is
intentionally NOT hideable.
"""
from __future__ import annotations

import logging
import threading

from .config import Config

log = logging.getLogger(__name__)


def _make_icon_image():
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGB", (size, size), (34, 40, 49))
    d = ImageDraw.Draw(img)
    # A simple "eye" glyph to signal monitoring.
    d.ellipse((8, 20, 56, 44), outline=(120, 180, 255), width=3)
    d.ellipse((26, 26, 38, 38), fill=(120, 180, 255))
    return img


class Tray:
    """Runs a pystray icon on its own thread. Falls back to a no-op if the
    tray backend is unavailable (e.g. headless/service context)."""

    def __init__(self, config: Config, on_quit=None):
        self.config = config
        self._on_quit = on_quit
        self._icon = None
        self._thread: threading.Thread | None = None

    def _build(self):
        import pystray

        def show_notice(icon, item):
            self._show_notice()

        menu = pystray.Menu(
            pystray.MenuItem("What is monitored", show_notice, default=True),
            pystray.MenuItem("Contact admin", lambda i, it: self._show_contact()),
            pystray.MenuItem("Quit", self._quit),
        )
        return pystray.Icon(
            "monitor-com",
            _make_icon_image(),
            "monitor-com — activity monitoring is active",
            menu,
        )

    def _show_notice(self):
        body = self.config.consent.notice
        if self.config.consent.contact:
            body += f"\n\nContact: {self.config.consent.contact}"
        self._message_box("Monitoring notice", body)

    def _show_contact(self):
        self._message_box(
            "Contact", self.config.consent.contact or "No contact configured."
        )

    @staticmethod
    def _message_box(title: str, body: str):
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo(title, body)
            root.destroy()
        except Exception:  # noqa: BLE001
            log.info("%s: %s", title, body)

    def _quit(self, icon, item):
        if self._on_quit:
            self._on_quit()
        if self._icon:
            self._icon.stop()

    def start(self) -> None:
        try:
            self._icon = self._build()
        except Exception as exc:  # noqa: BLE001
            log.warning("Tray icon unavailable (%s); continuing without it.", exc)
            return
        self._thread = threading.Thread(
            target=self._icon.run, name="tray", daemon=True
        )
        self._thread.start()
        log.info("Tray icon active (monitoring is visible to the user).")

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:  # noqa: BLE001
                pass
