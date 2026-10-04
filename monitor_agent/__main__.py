"""Console entry point: `python -m monitor_agent` or `monitor-com`.

Loads config, gates on consent, starts the tray icon and the collectors, and
runs until interrupted.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys

from .config import Config
from .consent import ensure_consent
from .scheduler import Agent
from .tray import Tray


def _parse_args(argv):
    p = argparse.ArgumentParser(
        prog="monitor-com",
        description=(
            "Transparent, consent-based employee activity monitoring agent. "
            "See docs/ACCEPTABLE_USE.md — only for devices you own/administer, "
            "with notice and lawful basis."
        ),
    )
    p.add_argument("--config", "-c", default=None, help="Path to config.yaml")
    p.add_argument(
        "--no-tray",
        action="store_true",
        help="Do not show the tray icon (not recommended; reduces transparency).",
    )
    p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt for consent; require it to already be on record.",
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("monitor_agent")

    config = Config.load(args.config)
    agent = Agent(config)

    interactive = (not args.non_interactive) and sys.stdin is not None and sys.stdin.isatty()
    # The tray can also surface the notice, but consent must be recorded before
    # any collection begins.
    if not ensure_consent(config, agent.storage, interactive=interactive):
        log.error("Consent not established; exiting without collecting anything.")
        agent.storage.close()
        return 2

    tray = None
    if not args.no_tray:
        tray = Tray(config, on_quit=agent.stop)
        tray.start()

    # Graceful shutdown on SIGINT/SIGTERM.
    def _handle(signum, _frame):
        log.info("Received signal %s; shutting down.", signum)
        agent.stop()

    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", signal.SIGINT)):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):
            pass  # not on main thread / not supported

    try:
        agent.run_forever()
    finally:
        if tray is not None:
            tray.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
