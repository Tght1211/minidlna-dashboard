#!/bin/bash
# Run minidlna-dashboard in foreground (for testing or launchd ProgramArguments).
set -euo pipefail
cd "$(dirname "$0")/.."
# -u: unbuffered stdout/stderr (matters when launchd redirects to log files)
exec .venv/bin/python -u app.py
