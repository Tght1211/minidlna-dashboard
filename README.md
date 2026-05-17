# minidlna-dashboard

A tiny Flask companion for the minidlna server running on this Mac. Replaces
minidlna's built-in (and unmodifiable) status page on port 8200 with a real
dashboard on port 8201.

## Features

- **Overview** — counts, total size, scan status, connected DLNA clients,
  media-dir disk usage, recent additions with thumbnails.
- **Browse** — folder grid + per-folder item view, full-text search across
  title/artist/album/path, in-browser HTML5 playback, copy DLNA stream URL.
- **Settings** — add/remove media directories (writes minidlna.conf + restart),
  log tail, batch thumbnail generation.
- **Auto-sync** — polls each media_dir's top-level entries every 30s; on
  change, debounces 30s then `SIGHUP`s minidlna for an incremental rescan.

## Install (one-shot)

```
./scripts/install.sh
```

Sets up a venv, installs Flask, writes `~/Library/LaunchAgents/local.minidlna-dashboard.plist`,
starts it via `launchctl`. Reach the dashboard at `http://<lan-ip>:8201/`.

## Layout

```
app.py          Flask app + routes
lib/db.py       read-only files.db queries
lib/status.py   process + lsof-derived runtime status
lib/config.py   minidlna.conf parser/writer
lib/thumbs.py   ffmpeg thumbnail generator (cached)
lib/watcher.py  custom polling-based auto-rescan
templates/      Jinja2 templates
static/         CSS + JS
scripts/        install.sh / uninstall.sh / run.sh
```

## Why a custom poller instead of watchdog/FSEvents?

Two macOS gotchas:
1. minidlna's built-in `inotify=yes` does use kqueue, but it opens one fd per
   directory; large backup trees (Android phone dumps, etc.) hit EMFILE.
2. launchd-spawned processes have a separate TCC identity; FSEvents calls into
   `/Volumes/...` hang in `FSEventStreamCreate`, and watchdog's
   `PollingObserver` deadlocks during its initial DirectorySnapshot.

A 30-line `os.scandir` poller on each media_dir's top level avoids both. The
user's pattern (drop in a new subfolder) is detected within 30s, then a single
SIGHUP lets minidlna do its own deep rescan.
