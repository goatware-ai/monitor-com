from pathlib import Path

from monitor_agent.config import Config


def test_defaults_when_no_file():
    cfg = Config.load(None)
    assert cfg.screenshots.enabled is True
    assert cfg.keystrokes.window_seconds == 60
    assert "chrome" in cfg.browser.browsers


def test_load_yaml_and_unknown_keys_ignored(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(
        """
screenshots:
  enabled: false
  interval_seconds: 42
  bogus_key: 1
keystrokes:
  window_seconds: 30
consent:
  preacknowledged: true
""",
        encoding="utf-8",
    )
    cfg = Config.load(p)
    assert cfg.screenshots.enabled is False
    assert cfg.screenshots.interval_seconds == 42
    assert cfg.keystrokes.window_seconds == 30
    assert cfg.consent.preacknowledged is True


def test_storage_paths_expand(monkeypatch, tmp_path):
    monkeypatch.setenv("MONITOR_TEST_ROOT", str(tmp_path))
    cfg = Config.load(None)
    cfg.storage.root = "$MONITOR_TEST_ROOT/mc"
    assert cfg.storage.root_path == tmp_path / "mc"
    assert cfg.storage.database_path == tmp_path / "mc" / "monitor.db"
