#!/bin/bash
# run_job.sh - Job lifecycle wrapper that logs start/end events
# Usage: run_job.sh <job_name> <command> [args...]

MONITOR_DIR="${MONITOR_DIR:-$HOME/monitor}"
OUT_DIR="$MONITOR_DIR/out"
EVENTS_LOG="$OUT_DIR/events.log"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <job_name> <command> [args...]" >&2
    exit 1
fi

job_name="$1"
shift
command="$@"

# Ensure output directory exists
mkdir -p "$OUT_DIR"

# Log job start
start_time=$(date '+%Y-%m-%d %H:%M')
echo "$start_time job=$job_name start" >> "$EVENTS_LOG"

# Run the command and capture exit code
$command
exit_code=$?

# Log job end
end_time=$(date '+%Y-%m-%d %H:%M')
echo "$end_time job=$job_name end rc=$exit_code" >> "$EVENTS_LOG"

exit $exit_code

