#!/bin/bash
# cpu.sh - Read raw CPU counters from /proc/stat
# Output: total_ticks idle_ticks

read -r cpu user nice system idle iowait irq softirq steal guest guest_nice < /proc/stat

# Calculate total ticks (sum of all CPU time)
total_ticks=$((user + nice + system + idle + iowait + irq + softirq + steal + guest + guest_nice))

echo "$total_ticks $idle"

