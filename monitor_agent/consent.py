"""Consent gating.

The agent must not begin collecting until consent is acknowledged. This module
decides whether consent is already on record, and (when running interactively)
presents the notice and records the acknowledgement.

This is a deliberate guardrail: transparent, consent-based monitoring is the
only supported use of this software (see docs/ACCEPTABLE_USE.md).
"""
from __future__ import annotations

import logging

from .config import Config
from .storage import Storage

log = logging.getLogger(__name__)


def ensure_consent(config: Config, storage: Storage, interactive: bool) -> bool:
    """Return True if collection may proceed.

    Order of precedence:
      1. An existing acknowledgement in the database.
      2. `consent.preacknowledged: true` in config (operator attests consent was
         captured out of band, e.g. via a signed acceptable-use policy).
      3. An interactive notice the user acknowledges now.
    Otherwise returns False and collection does not start.
    """
    existing = storage.get_consent()
    if existing is not None and existing["acknowledged"]:
        log.info("Consent already on record; collection permitted.")
        return True

    if config.consent.preacknowledged:
        storage.record_consent(config.consent.notice)
        log.info("Consent pre-acknowledged via configuration; recorded.")
        return True

    if interactive:
        return _prompt(config, storage)

    log.warning(
        "No consent on record and not running interactively. Collection will "
        "NOT start. Run once in the foreground to show the notice, or set "
        "consent.preacknowledged in the config if consent was captured by your "
        "onboarding process."
    )
    return False


def _prompt(config: Config, storage: Storage) -> bool:
    """Show the monitoring notice and record acknowledgement.

    Tries a GUI dialog; falls back to the console. Acknowledgement is required.
    """
    notice = config.consent.notice
    contact = config.consent.contact
    body = notice + (f"\n\nContact: {contact}" if contact else "")

    # Try a native dialog first so it is visible even for background launches
    # started from a shortcut.
    try:  # pragma: no cover - GUI path not exercised in tests
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        agreed = messagebox.askokcancel(
            "Monitoring notice",
            body + "\n\nClick OK to acknowledge and continue.",
        )
        root.destroy()
        if agreed:
            storage.record_consent(notice)
            log.info("Consent acknowledged via dialog.")
            return True
        log.warning("Consent declined; collection will not start.")
        return False
    except Exception:  # noqa: BLE001 - fall back to console
        pass

    print("\n" + "=" * 70)
    print("MONITORING NOTICE")
    print("=" * 70)
    print(body)
    print("-" * 70)
    try:
        answer = input("Type 'I AGREE' to acknowledge and continue: ").strip()
    except EOFError:
        answer = ""
    if answer.upper() == "I AGREE":
        storage.record_consent(notice)
        log.info("Consent acknowledged via console.")
        return True
    log.warning("Consent not given; collection will not start.")
    return False
