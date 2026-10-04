"""Screenshot collector.

Captures the desktop at a configured interval and writes PNG/JPEG files to the
storage root, recording metadata in the database. Uses `mss` which works on
Windows, macOS and Linux (so the module is importable and testable anywhere).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from ..config import ScreenshotConfig
from ..storage import Storage

log = logging.getLogger(__name__)


class ScreenshotCollector:
    def __init__(self, config: ScreenshotConfig, storage: Storage, root: Path):
        self.config = config
        self.storage = storage
        self.dir = Path(root) / "screenshots"
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def interval(self) -> int:
        return max(1, int(self.config.interval_seconds))

    def collect_once(self) -> int:
        """Capture one round of screenshots. Returns number of images saved."""
        try:
            import mss  # imported lazily so the package imports without a display
            from PIL import Image
        except Exception as exc:  # noqa: BLE001
            log.error("Screenshot dependencies unavailable: %s", exc)
            return 0

        saved = 0
        ts = datetime.now()
        stamp = ts.strftime("%Y%m%d-%H%M%S")
        try:
            with mss.mss() as sct:
                # monitors[0] is the virtual "all screens" bounding box; the
                # real monitors start at index 1.
                monitors = sct.monitors
                targets = (
                    list(range(1, len(monitors)))
                    if self.config.all_monitors and len(monitors) > 1
                    else [1 if len(monitors) > 1 else 0]
                )
                for mon_index in targets:
                    shot = sct.grab(monitors[mon_index])
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    img = self._maybe_downscale(img)
                    path = self._save(img, stamp, mon_index)
                    self.storage.add_screenshot(
                        str(path), mon_index, img.width, img.height
                    )
                    saved += 1
        except Exception as exc:  # noqa: BLE001
            log.error("Screenshot capture failed: %s", exc)
        if saved:
            log.debug("Saved %d screenshot(s) at %s", saved, stamp)
        return saved

    def _maybe_downscale(self, img):
        w = int(self.config.downscale_width or 0)
        if w and img.width > w:
            from PIL import Image

            ratio = w / img.width
            img = img.resize((w, max(1, int(img.height * ratio))), Image.LANCZOS)
        return img

    def _save(self, img, stamp: str, mon_index: int) -> Path:
        fmt = (self.config.format or "png").lower()
        day_dir = self.dir / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        if fmt == "jpeg" or fmt == "jpg":
            path = day_dir / f"{stamp}-mon{mon_index}.jpg"
            img.save(path, "JPEG", quality=int(self.config.jpeg_quality))
        else:
            path = day_dir / f"{stamp}-mon{mon_index}.png"
            img.save(path, "PNG")
        return path
