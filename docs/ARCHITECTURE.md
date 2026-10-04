# Architecture

```
                         ┌──────────────────────┐
                         │   __main__ / service  │  entry points
                         └──────────┬───────────┘
                                    │ loads
                         ┌──────────▼───────────┐
                         │        Config         │  config.yaml → dataclasses
                         └──────────┬───────────┘
                                    │
             consent gate ─────────►│  ensure_consent()  (must pass first)
                                    │
                         ┌──────────▼───────────┐
                         │        Agent          │  scheduler.py
                         │  (owns Storage + the  │
                         │   collector threads)  │
                         └───┬───────┬───────┬───┘
            poll interval    │       │       │    streaming listener
          ┌──────────────────┘       │       └──────────────────┐
          ▼                          ▼                          ▼
 ScreenshotCollector      BrowserUrlCollector      KeystrokeActivityCollector
   (mss → PNG/JPEG)         (reads browser           (pynput → COUNTS only,
                             history DBs)             key identity discarded)
          │                          │                          │
          └──────────────┬──────────┴──────────────┬───────────┘
                         ▼                          ▼
                   ┌──────────────────────────────────┐
                   │             Storage               │  SQLite + files
                   │  screenshots/ *.png               │
                   │  monitor.db: screenshots,         │
                   │  browser_urls, keystroke_counts,  │
                   │  consent                          │
                   └──────────────────────────────────┘

   Tray (pystray) runs alongside — always-visible "monitoring is active" icon.
   Retention task periodically purges data older than retention.days.
```

## Threading model

- Each **polling** collector (screenshots, browser URLs, retention) runs on its
  own daemon thread via `_PollWorker`, which calls `collect_once()` then waits
  `interval` seconds on a shared stop event.
- The **keystroke** collector installs a global `pynput` listener and runs a
  flush thread that writes one `keystroke_counts` row per window.
- `Storage` serializes all DB access behind a lock, so collectors can write
  concurrently.
- `Agent.stop()` sets the stop event, stops the listener, flushes the final
  keystroke window, joins workers, and closes the DB.

## Data model

| Table | Contents |
|---|---|
| `consent` | single row recording that the notice was acknowledged + when |
| `screenshots` | timestamp, file path, monitor index, dimensions |
| `browser_urls` | timestamp, browser, url, title, visit time (deduped) |
| `keystroke_counts` | window start/end + **count** (never key identity) |

## Extending

To add an export/reporting backend, read from `monitor.db` out of band, or add a
collector-style uploader. If you transmit data off the device, you are
responsible for securing it and for the lawful basis of that transfer
(see `docs/ACCEPTABLE_USE.md`).
