#!/bin/sh
# Loest den GitHub-Workflow aus, aber nur an Tagen, an denen es etwas zu holen
# gibt. Wird vom Cron auf dem Trigger-Host aufgerufen, siehe README.
set -u

REPO="MichaelOv/leibniz-stundenplan"
DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
LOG="${LEIBNIZ_LOG:-/var/log/leibniz-cron.log}"

if ! "$DIR/venv/bin/python" "$DIR/scripts/ist_schultag.py" >/dev/null 2>&1; then
    exit 0
fi

HOME="${HOME:-/root}" /usr/bin/gh workflow run update.yml --repo "$REPO" >>"$LOG" 2>&1
