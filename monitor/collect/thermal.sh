#!/bin/bash
# thermal.sh - Read CPU temperature from /sys/class/thermal
# Output: temperature_celsius

# Find the first thermal zone that has a temperature reading
# Usually thermal_zone0 is CPU temperature
temp_file=$(find /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -1)

if [ -n "$temp_file" ] && [ -r "$temp_file" ]; then
    # Temperature is in millidegrees Celsius, convert to Celsius
    temp_millidegrees=$(cat "$temp_file")
    temperature_celsius=$((temp_millidegrees / 1000))
    echo "$temperature_celsius"
else
    # Fallback: return 0 if thermal sensors are not available
    echo "0"
fi

