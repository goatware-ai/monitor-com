"""Windows service wrapper (optional).

Lets the agent run as a background Windows service while remaining fully visible
in the Services console and Task Manager — no hiding. Requires pywin32 and only
imports it on Windows.

Install/uninstall is normally driven by scripts/install_service.ps1, which calls:

    python -m monitor_agent.service install
    python -m monitor_agent.service start
    python -m monitor_agent.service stop
    python -m monitor_agent.service remove

The config path is read from the MONITOR_COM_CONFIG environment variable (set
for the service by the install script).
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)

CONFIG_ENV_VAR = "MONITOR_COM_CONFIG"


def _build_service_class():
    # Imported lazily; only available on Windows with pywin32 installed.
    import servicemanager  # type: ignore
    import win32event  # type: ignore
    import win32service  # type: ignore
    import win32serviceutil  # type: ignore

    from .config import Config
    from .consent import ensure_consent
    from .scheduler import Agent

    class MonitorComService(win32serviceutil.ServiceFramework):
        _svc_name_ = "MonitorCom"
        _svc_display_name_ = "monitor-com Activity Monitoring Agent"
        _svc_description_ = (
            "Transparent, consent-based employee activity monitoring. Visible "
            "to users; collects screenshots, browser URLs and keystroke counts "
            "per configuration."
        )

        def __init__(self, args):
            super().__init__(args)
            self._stop_evt = win32event.CreateEvent(None, 0, 0, None)
            self._agent: Agent | None = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self._agent is not None:
                self._agent.stop()
            win32event.SetEvent(self._stop_evt)

        def SvcDoRun(self):
            servicemanager.LogInfoMsg("monitor-com service starting")
            config_path = os.environ.get(CONFIG_ENV_VAR)
            config = Config.load(config_path)
            self._agent = Agent(config)
            # In service context there is no interactive session; require consent
            # to already be on record (or pre-acknowledged in config).
            if not ensure_consent(config, self._agent.storage, interactive=False):
                servicemanager.LogErrorMsg(
                    "monitor-com: consent not on record; refusing to collect. "
                    "Run once interactively to acknowledge the notice, or set "
                    "consent.preacknowledged in the config."
                )
                return
            self._agent.start()
            win32event.WaitForSingleObject(self._stop_evt, win32event.INFINITE)
            servicemanager.LogInfoMsg("monitor-com service stopped")

    return MonitorComService


def main(argv: list[str] | None = None) -> None:
    """Entry point for `python -m monitor_agent.service <command>`.

    Delegates to pywin32's service command handler (install/start/stop/remove).
    """
    if sys.platform != "win32":
        raise SystemExit("The Windows service wrapper is only available on Windows.")
    import win32serviceutil  # type: ignore

    service_cls = _build_service_class()
    win32serviceutil.HandleCommandLine(service_cls, argv=argv or sys.argv)


if __name__ == "__main__":
    main()
