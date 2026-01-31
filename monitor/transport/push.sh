#!/bin/bash
# push.sh - Push metrics and logs to remote storage (Raspberry Pi)
# Usage: push.sh [destination]
# Destination format: user@host:/path/to/destination

MONITOR_DIR="${MONITOR_DIR:-$HOME/monitor}"
OUT_DIR="$MONITOR_DIR/out"
DEFAULT_DEST="${PUSH_DEST:-}"

destination="${1:-$DEFAULT_DEST}"

if [ -z "$destination" ]; then
    echo "Usage: $0 [user@host:/path]" >&2
    echo "Or set PUSH_DEST environment variable" >&2
    exit 1
fi

# Extract host and path from destination
if [[ "$destination" =~ ^([^:]+):(.+)$ ]]; then
    host="${BASH_REMATCH[1]}"
    remote_path="${BASH_REMATCH[2]}"
else
    echo "Invalid destination format. Use: user@host:/path" >&2
    exit 1
fi

# Push metrics.json and events.log using rsync (preferred) or scp
if command -v rsync >/dev/null 2>&1; then
    # Use rsync for efficient incremental transfers
    rsync -avz --append "$OUT_DIR/metrics.json" "$OUT_DIR/events.log" "$destination/" 2>/dev/null
    exit_code=$?
elif command -v scp >/dev/null 2>&1; then
    # Fallback to scp
    scp "$OUT_DIR/metrics.json" "$OUT_DIR/events.log" "$destination/" 2>/dev/null
    exit_code=$?
else
    echo "Error: Neither rsync nor scp found. Install one to enable transport." >&2
    exit 1
fi

if [ $exit_code -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M') Push successful to $destination" >> "$OUT_DIR/transport.log"
else
    echo "$(date '+%Y-%m-%d %H:%M') Push failed to $destination" >> "$OUT_DIR/transport.log"
fi

exit $exit_code

