# monitor-com

A **transparent, consent-based employee activity monitoring agent for Windows.**

`monitor-com` is a background agent that collects workplace productivity signals
on company-managed Windows PCs:

- 📸 **Periodic screenshots** of the desktop
- 🌐 **Visited browser URLs** (from the browser's own history databases)
- ⌨️ **Keystroke *counts* per minute** — an activity level metric only

It is designed for **lawful, disclosed workplace monitoring**: the people being
monitored are shown a notice, the agent is **visible in the system tray** and in
Task Manager, and it does **not** attempt to hide itself or evade detection.

> [!IMPORTANT]
> **Read [`docs/ACCEPTABLE_USE.md`](docs/ACCEPTABLE_USE.md) before deploying.**
> This software is intended **only** for monitoring devices you own or
> administer, by people who have been **notified and have consented**, in
> compliance with the laws of your jurisdiction. Deploying it covertly on
> devices you do not control, or on people without lawful basis and notice, is
> illegal in most places and is not a supported use case.

---

## Why it's built this way

The feature set of legitimate employee monitoring overlaps technically with
"stalkerware". The difference is **transparency and consent**. `monitor-com`
bakes the right side of that line into the product:

| Design choice | Why |
|---|---|
| Keystroke **counts**, never key content | Measures activity level without capturing passwords, messages, or any typed content. There is no keylogger. |
| **Required consent acknowledgement** on first run | The agent will not start collecting until consent is recorded. |
| Always-visible **system tray icon** with a "What is monitored" screen | The monitored person can always see it is running and what it does. |
| Runs under the user's normal account, listed in Task Manager | No rootkit, no process hiding, no anti-tamper. |
| All data stored **locally** by default | You control where data goes; nothing is exfiltrated to a third party. |
| Every collector can be disabled in config | Collect only what you have a lawful basis to collect. |
| Configurable **retention / auto-purge** | Don't keep data longer than needed. |

If you need covert, hidden, or anti-detection behavior, this is the wrong tool
and that request is explicitly out of scope.

---

## Features

### Screenshots
Captures the screen at a configurable interval using [`mss`](https://pypi.org/project/mss/),
stores PNGs to a local directory, and records metadata in SQLite. Supports
multiple monitors and optional downscaling to save space.

### Browser URLs
Reads visited URLs from the browser's **own history database** (Chrome, Edge,
Firefox). It does not intercept network traffic or inject into the browser — it
reads the same history the user can see in their browser. Deduplicated by visit.

### Keystroke activity
Counts key-press events per one-minute window via a global listener, and stores
only the **count** for each window. **The identity of the keys is discarded
immediately and never stored.** This yields an "activity level" signal (e.g.
keystrokes/minute) without any content capture.

---

## Installation

Requires Python 3.10+ on Windows.

```powershell
git clone <this-repo>
cd monitor-com
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Configuration

Copy the example config and edit it:

```powershell
copy config.example.yaml config.yaml
```

See `config.example.yaml` for all options. Key sections: `storage`,
`screenshots`, `browser`, `keystrokes`, `consent`, `retention`.

## Running

Foreground (recommended for first run — shows the consent notice):

```powershell
python -m monitor_agent --config config.yaml
```

As a background Windows service (runs under an account, still visible in
Services and Task Manager):

```powershell
# from an elevated PowerShell
.\scripts\install_service.ps1 -ConfigPath C:\ProgramData\monitor-com\config.yaml
```

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for service details and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pieces fit together.

## Data & privacy

- Default storage root: `%ProgramData%\monitor-com\` (configurable).
- SQLite database `monitor.db` holds metadata; screenshots are PNG files.
- Nothing is uploaded anywhere by this agent. If you build a reporting backend,
  you are responsible for securing it and for the lawful basis of that transfer.

## License

See [`LICENSE`](LICENSE). Use is additionally subject to
[`docs/ACCEPTABLE_USE.md`](docs/ACCEPTABLE_USE.md).
