#!/bin/bash
# setup_cron.sh - Setup cron jobs for metric collection
# This script adds cron entries to run snapshot.sh every 15 seconds

MONITOR_DIR="${MONITOR_DIR:-$HOME/monitor}"
SNAPSHOT_SCRIPT="$MONITOR_DIR/snapshot.sh"

if [ ! -f "$SNAPSHOT_SCRIPT" ]; then
    echo "Error: snapshot.sh not found at $SNAPSHOT_SCRIPT" >&2
    exit 1
fi

# Make scripts executable
chmod +x "$SNAPSHOT_SCRIPT"
chmod +x "$MONITOR_DIR/collect"/*.sh
chmod +x "$MONITOR_DIR/jobs"/*.sh
chmod +x "$MONITOR_DIR/transport"/*.sh

# Create cron entries for 15-second intervals
# Pattern: run at :00, :15, :30, :45 of every minute
CRON_ENTRIES=(
    "* * * * * $SNAPSHOT_SCRIPT"
    "* * * * * sleep 15 && $SNAPSHOT_SCRIPT"
    "* * * * * sleep 30 && $SNAPSHOT_SCRIPT"
    "* * * * * sleep 45 && $SNAPSHOT_SCRIPT"
)

# Check if entries already exist
CRON_TEMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "$SNAPSHOT_SCRIPT" > "$CRON_TEMP" || true

# Add new entries
for entry in "${CRON_ENTRIES[@]}"; do
    echo "$entry" >> "$CRON_TEMP"
done

# Install new crontab
crontab "$CRON_TEMP"
rm "$CRON_TEMP"

echo "Cron jobs installed successfully."
echo "Snapshot script will run every 15 seconds."
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove cron jobs: crontab -e"

