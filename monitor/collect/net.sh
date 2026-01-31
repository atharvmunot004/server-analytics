#!/bin/bash
# net.sh - Read network counters from /proc/net/dev
# Output: interface rx_bytes tx_bytes
# Aggregates all physical network interfaces

rx_bytes=0
tx_bytes=0

# Read /proc/net/dev and sum bytes for all interfaces (skip loopback)
while read -r line; do
    # Skip header lines
    if [[ "$line" =~ ^(Inter-| face) ]]; then
        continue
    fi
    
    # Extract interface name and stats
    interface=$(echo "$line" | awk -F: '{print $1}' | xargs)
    stats=$(echo "$line" | awk -F: '{print $2}')
    
    # Skip loopback interface
    if [[ "$interface" == "lo" ]]; then
        continue
    fi
    
    # Extract rx_bytes (field 1) and tx_bytes (field 9)
    rx=$(echo "$stats" | awk '{print $1}')
    tx=$(echo "$stats" | awk '{print $9}')
    
    if [ -n "$rx" ] && [ -n "$tx" ]; then
        rx_bytes=$((rx_bytes + rx))
        tx_bytes=$((tx_bytes + tx))
    fi
done < /proc/net/dev

echo "$rx_bytes $tx_bytes"

