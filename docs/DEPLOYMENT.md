# Deployment

## Prerequisites

- Windows 10/11 (or Windows Server) with Python 3.10+.
- The agent installed (`pip install -e .`) and a `config.yaml`.
- A completed compliance step: users notified, lawful basis in place
  (see `docs/ACCEPTABLE_USE.md`).

## 1. First run (records consent)

Run once in the foreground so the monitoring notice appears and consent is
recorded in the database:

```powershell
python -m monitor_agent --config C:\ProgramData\monitor-com\config.yaml
```

The user acknowledges the notice; the agent then begins collecting and shows a
tray icon. Press Ctrl+C (or use the tray "Quit") to stop.

If your organization captures consent through a signed acceptable-use policy
instead, set `consent.preacknowledged: true` in the config. You remain
responsible for having given notice and for your lawful basis.

## 2. Run as a background service

From an **elevated** PowerShell:

```powershell
.\scripts\install_service.ps1 -ConfigPath C:\ProgramData\monitor-com\config.yaml
```

This installs the `MonitorCom` service (startup: automatic) and starts it. The
service:

- Appears in `services.msc` and in Task Manager (it does not hide).
- Reads its config path from the machine environment variable
  `MONITOR_COM_CONFIG`.
- **Refuses to collect** if consent is not on record and not pre-acknowledged.

Manage it with standard tooling:

```powershell
python -m monitor_agent.service stop
python -m monitor_agent.service start
python -m monitor_agent.service remove   # uninstall
```

### Service account & sessions

- To capture screenshots and keystroke activity the agent must run in the
  user's interactive session. Running as a per-user startup task (e.g. a
  Scheduled Task "at log on", or a shortcut in the Startup folder) is often
  simpler than a session-0 service for interactive capture.
- A session-0 service cannot see the interactive desktop; prefer the per-user
  approach for screenshot/keystroke collectors, and reserve the service model
  for machine-wide, non-interactive signals.

## 3. Storage & retention

- Data lives under `storage.root` (default `%ProgramData%\monitor-com`).
- Set `retention.days` to auto-purge old data. Keep only what you need.

## 4. Uninstall

```powershell
python -m monitor_agent.service stop
python -m monitor_agent.service remove
[Environment]::SetEnvironmentVariable("MONITOR_COM_CONFIG", $null, "Machine")
```

Then remove the storage directory if you no longer need the data.
