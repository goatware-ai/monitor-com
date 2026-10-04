"""Configuration loading and typed access.

Reads the YAML config file and exposes it as nested dataclasses with sensible
defaults, so the rest of the agent never touches raw dicts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _expand(path: str) -> str:
    """Expand Windows (%VAR%) and POSIX ($VAR / ~) variables in a path."""
    return os.path.expanduser(os.path.expandvars(path))


@dataclass
class StorageConfig:
    root: str = "%ProgramData%\\monitor-com"
    database: str = "monitor.db"

    @property
    def root_path(self) -> Path:
        return Path(_expand(self.root))

    @property
    def database_path(self) -> Path:
        return self.root_path / self.database


@dataclass
class ConsentConfig:
    preacknowledged: bool = False
    notice: str = (
        "This company-managed device is monitored for security and "
        "productivity. Collected: periodic screenshots, visited website "
        "addresses, and keyboard activity levels (counts only, not what you "
        "type). Contact your IT administrator with questions."
    )
    contact: str = ""


@dataclass
class ScreenshotConfig:
    enabled: bool = True
    interval_seconds: int = 300
    all_monitors: bool = True
    downscale_width: int = 1280
    format: str = "png"
    jpeg_quality: int = 70


@dataclass
class BrowserConfig:
    enabled: bool = True
    poll_seconds: int = 600
    browsers: list[str] = field(default_factory=lambda: ["chrome", "edge", "firefox"])


@dataclass
class KeystrokeConfig:
    enabled: bool = True
    window_seconds: int = 60


@dataclass
class RetentionConfig:
    days: int = 30
    purge_check_hours: int = 24


@dataclass
class Config:
    storage: StorageConfig = field(default_factory=StorageConfig)
    consent: ConsentConfig = field(default_factory=ConsentConfig)
    screenshots: ScreenshotConfig = field(default_factory=ScreenshotConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    keystrokes: KeystrokeConfig = field(default_factory=KeystrokeConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)

    @classmethod
    def load(cls, path: str | os.PathLike | None) -> "Config":
        """Load config from a YAML file, falling back to defaults for any
        missing section or key."""
        data: dict = {}
        if path is not None:
            p = Path(path)
            if p.exists():
                with p.open("r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}

        def section(name: str, klass):
            raw = data.get(name) or {}
            # Only pass keys the dataclass knows about, so unknown keys in the
            # YAML don't crash the agent.
            known = {f.name for f in klass.__dataclass_fields__.values()}
            return klass(**{k: v for k, v in raw.items() if k in known})

        return cls(
            storage=section("storage", StorageConfig),
            consent=section("consent", ConsentConfig),
            screenshots=section("screenshots", ScreenshotConfig),
            browser=section("browser", BrowserConfig),
            keystrokes=section("keystrokes", KeystrokeConfig),
            retention=section("retention", RetentionConfig),
        )
