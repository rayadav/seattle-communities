#!/bin/bash
set -euo pipefail

# Directory of this repository
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# Ensure common paths (python3, git, etc.) are available to launchd
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Log file
LOG_DIR="$HOME/Library/Logs"
if ! touch "$LOG_DIR/.test_write" 2>/dev/null; then
    LOG_DIR="$REPO_DIR/logs"
    mkdir -p "$LOG_DIR"
else
    rm -f "$LOG_DIR/.test_write" 2>/dev/null || true
fi
LOG_FILE="$LOG_DIR/seattle-communities-updater.log"

exec >> "$LOG_FILE" 2>&1

echo "=========================================="
echo "Run started: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Working directory: $REPO_DIR"

# Load environment variables if .env exists
if [ -f "$REPO_DIR/.env" ]; then
    echo "Loading environment variables from .env..."
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

# Optional: Sync with remote repository before running
if git remote get-url origin >/dev/null 2>&1; then
    echo "Pulling latest changes from origin/main..."
    git pull --rebase origin main || echo "Warning: git pull failed, proceeding with current local state."
fi

# Run the event updater script
echo "Running auto_update_events.py..."
python3 "$REPO_DIR/scripts/auto_update_events.py"

# Commit and push if events.json changed
if ! git diff --quiet events.json; then
    echo "Changes detected in events.json. Committing and pushing..."
    git add events.json events.min.json 2>/dev/null || git add events.json
    git commit -m "Auto-update community events [skip ci]"
    if git push origin main; then
        echo "Successfully pushed updates to origin/main."
    else
        echo "Warning: git push failed. Changes remain committed locally."
    fi
else
    echo "No changes to events.json."
fi

echo "Run completed: $(date '+%Y-%m-%d %H:%M:%S %Z')"
