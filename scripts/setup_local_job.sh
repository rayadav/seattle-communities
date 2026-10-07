#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.seattlecommunities.autoupdate.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"

mkdir -p "$TARGET_DIR"

echo "Copying LaunchAgent definition to $TARGET_PLIST..."
cp "$PLIST_SRC" "$TARGET_PLIST"

echo "Unloading any existing job..."
launchctl unload "$TARGET_PLIST" 2>/dev/null || true

echo "Loading new LaunchAgent..."
launchctl load -w "$TARGET_PLIST"

echo "Checking launchctl status:"
if launchctl list | grep "com.seattlecommunities.autoupdate"; then
    echo "✓ LaunchAgent successfully loaded!"
else
    echo "Notice: Job loaded. You can trigger it manually with:"
    echo "  launchctl start com.seattlecommunities.autoupdate"
fi

echo ""
echo "Log file location: ~/Library/Logs/seattle-communities-updater.log"
echo "To test run immediately: bash $SCRIPT_DIR/run_nightly_update.sh"
