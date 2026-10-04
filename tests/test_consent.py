from monitor_agent.config import Config
from monitor_agent.consent import ensure_consent
from monitor_agent.storage import Storage


def test_non_interactive_without_consent_blocks(tmp_path):
    cfg = Config.load(None)
    s = Storage(tmp_path / "m.db")
    assert ensure_consent(cfg, s, interactive=False) is False
    s.close()


def test_preacknowledged_records_and_allows(tmp_path):
    cfg = Config.load(None)
    cfg.consent.preacknowledged = True
    s = Storage(tmp_path / "m.db")
    assert ensure_consent(cfg, s, interactive=False) is True
    assert s.get_consent()["acknowledged"] == 1
    s.close()


def test_existing_consent_allows(tmp_path):
    cfg = Config.load(None)
    s = Storage(tmp_path / "m.db")
    s.record_consent("already agreed")
    assert ensure_consent(cfg, s, interactive=False) is True
    s.close()
