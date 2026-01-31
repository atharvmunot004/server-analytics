#!/bin/bash
# mem.sh - Read memory availability from /proc/meminfo
# Output: total_mb available_mb

# Read memory values in KB and convert to MB
total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}')
available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}')

# Convert KB to MB
total_mb=$((total_kb / 1024))
available_mb=$((available_kb / 1024))

echo "$total_mb $available_mb"

