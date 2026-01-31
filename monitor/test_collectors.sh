#!/bin/bash
# test_collectors.sh - Test all collector scripts individually
# Useful for debugging and verification

MONITOR_DIR="${MONITOR_DIR:-$HOME/monitor}"
COLLECT_DIR="$MONITOR_DIR/collect"

echo "Testing collector scripts..."
echo "================================"
echo ""

echo "1. CPU Collector:"
"$COLLECT_DIR/cpu.sh"
echo ""

echo "2. Memory Collector:"
"$COLLECT_DIR/mem.sh"
echo ""

echo "3. Thermal Collector:"
"$COLLECT_DIR/thermal.sh"
echo ""

echo "4. Disk Collector:"
"$COLLECT_DIR/disk.sh"
echo ""

echo "5. Network Collector:"
"$COLLECT_DIR/net.sh"
echo ""

echo "================================"
echo "Test complete. Check outputs above."

