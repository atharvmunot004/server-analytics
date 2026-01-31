#!/bin/bash
# disk.sh - Read disk IO counters from /proc/diskstats
# Output: device read_sectors write_sectors
# Aggregates all physical disks (excludes loop, ram, etc.)

read_sectors=0
write_sectors=0

# Read /proc/diskstats and sum sectors for physical disks
# Format: major minor name reads reads_merged reads_sectors reads_ms writes writes_merged writes_sectors writes_ms ...
while read -r major minor name rest; do
    # Skip loop devices, ram disks, and other non-physical devices
    if [[ "$name" =~ ^(loop|ram|fd|md|dm-) ]]; then
        continue
    fi
    
    # Extract read and write sectors (fields 6 and 10)
    read_s=$(echo "$rest" | awk '{print $1}')
    write_s=$(echo "$rest" | awk '{print $5}')
    
    if [ -n "$read_s" ] && [ -n "$write_s" ]; then
        read_sectors=$((read_sectors + read_s))
        write_sectors=$((write_sectors + write_s))
    fi
done < /proc/diskstats

echo "$read_sectors $write_sectors"

