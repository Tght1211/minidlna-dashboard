#!/bin/bash
# Install minidlna-dashboard as a per-user launchd agent.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="local.minidlna-dashboard"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/.cache/minidlna-dashboard/logs"

mkdir -p "$LOG_DIR"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "Creating Python venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
fi
"$PROJECT_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$PROJECT_DIR/.venv/bin/pip" install --quiet flask

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PROJECT_DIR}/scripts/run.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
EOF

UID_NUM=$(id -u)
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
launchctl kickstart -k "gui/${UID_NUM}/${LABEL}"

sleep 1
if launchctl print "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1; then
  echo "✓ Installed and started: ${LABEL}"
  echo "  Logs: ${LOG_DIR}/"
  echo "  URL:  http://$(ipconfig getifaddr en0 2>/dev/null || echo localhost):8201/"
else
  echo "✗ Failed to start. Check ${LOG_DIR}/stderr.log"
  exit 1
fi
