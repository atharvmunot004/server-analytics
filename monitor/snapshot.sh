#!/bin/bash
# snapshot.sh - Orchestrator script that collects all metrics and appends to metrics.json
# This script should be run every 15 seconds via cron
# Keeps only the last MAX_METRICS entries to prevent unbounded file growth

MONITOR_DIR="${MONITOR_DIR:-$HOME/monitor}"
COLLECT_DIR="$MONITOR_DIR/collect"
OUT_DIR="$MONITOR_DIR/out"
STATE_FILE="$OUT_DIR/.snapshot_state"
METRICS_FILE="$OUT_DIR/metrics.json"
MAX_METRICS="${MAX_METRICS:-100}"  # Maximum number of metrics to keep (default: 100)

# Ensure output directory exists
mkdir -p "$OUT_DIR"

# Get current timestamp (Unix epoch seconds)
ts=$(date +%s)

# Read CPU counters
cpu_output=$("$COLLECT_DIR/cpu.sh" 2>/dev/null || echo "0 0")
read -r total_ticks idle_ticks <<< "$cpu_output"

# Read memory
mem_output=$("$COLLECT_DIR/mem.sh" 2>/dev/null || echo "0 0")
read -r total_mb available_mb <<< "$mem_output"

# Read thermal
temperature_celsius=$("$COLLECT_DIR/thermal.sh" 2>/dev/null || echo "0")

# Read disk IO
disk_output=$("$COLLECT_DIR/disk.sh" 2>/dev/null || echo "0 0")
read -r read_sectors write_sectors <<< "$disk_output"

# Read network
net_output=$("$COLLECT_DIR/net.sh" 2>/dev/null || echo "0 0")
read -r rx_bytes tx_bytes <<< "$net_output"

# Read load average (1-minute)
load_1m=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo "0.0")

# Calculate CPU usage percentage (delta-based)
cpu_usage_percent=0.0
if [ -f "$STATE_FILE" ]; then
    # Read previous state
    read -r prev_total prev_idle < "$STATE_FILE"
    
    if [ -n "$prev_total" ] && [ -n "$prev_idle" ] && [ "$prev_total" -gt 0 ]; then
        # Calculate deltas
        total_delta=$((total_ticks - prev_total))
        idle_delta=$((idle_ticks - prev_idle))
        
        if [ "$total_delta" -gt 0 ]; then
            # CPU usage = (1 - idle_delta / total_delta) * 100
            # Use bc for floating point calculation if available, otherwise use awk
            # Use awk for formatting to ensure valid JSON (always includes leading zero)
            # This is more reliable than bc which can output .86 instead of 0.86
            cpu_usage_percent=$(awk "BEGIN {printf \"%.2f\", (1 - $idle_delta / $total_delta) * 100}")
            
            # Ensure non-negative
            if [ "$(echo "$cpu_usage_percent < 0" | awk '{print ($1 < 0)}')" -eq 1 ]; then
                cpu_usage_percent=0.0
            fi
        fi
    fi
fi

# Save current state for next run
echo "$total_ticks $idle_ticks" > "$STATE_FILE"

# Assemble JSON object
json=$(cat <<EOF
{"ts":$ts,"cpu":{"usage_percent":$cpu_usage_percent,"load_1m":$load_1m},"memory":{"available_mb":$available_mb,"total_mb":$total_mb},"thermal":{"cpu_temp_c":$temperature_celsius},"disk":{"read_sectors":$read_sectors,"write_sectors":$write_sectors},"network":{"rx_bytes":$rx_bytes,"tx_bytes":$tx_bytes}}
EOF
)

# Append to metrics.json (append-only)
echo "$json" >> "$METRICS_FILE"

# Keep only the last MAX_METRICS entries to prevent unbounded growth
# This reduces I/O operations and file size, improving performance
if [ -f "$METRICS_FILE" ]; then
    line_count=$(wc -l < "$METRICS_FILE" 2>/dev/null || echo "0")
    if [ "$line_count" -gt "$MAX_METRICS" ]; then
        # Keep only the last MAX_METRICS lines (most recent entries)
        # Use atomic write (temp file + move) to prevent corruption
        tail -n "$MAX_METRICS" "$METRICS_FILE" > "$METRICS_FILE.tmp" && mv "$METRICS_FILE.tmp" "$METRICS_FILE"
    fi
fi

