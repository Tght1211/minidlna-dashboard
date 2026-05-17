#!/bin/bash
set -euo pipefail
LABEL="local.minidlna-dashboard"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
UID_NUM=$(id -u)
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ Removed ${LABEL}"
