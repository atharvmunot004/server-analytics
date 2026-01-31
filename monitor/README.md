# Lightweight Node Monitor

A minimal, daemon-free system monitoring solution designed for HPC environments with low memory footprint (<50MB) and full user control.

## Design Goals

- **Lightweight**: No daemons, minimal dependencies
- **Low Memory**: <50MB footprint
- **HPC Friendly**: No high-cardinality labels, no per-rank overhead
- **User Control**: Simple shell scripts, easy to customize
- **No UI Dependencies**: Pure data collection

## Directory Structure

```
~/monitor/
├── collect/          # Metric collector scripts
│   ├── cpu.sh       # CPU counters
│   ├── mem.sh       # Memory stats
│   ├── thermal.sh   # CPU temperature
│   ├── disk.sh      # Disk I/O
│   └── net.sh       # Network I/O
├── jobs/            # Job lifecycle wrappers
│   └── run_job.sh   # Job execution wrapper
├── out/             # Append-only outputs
│   ├── metrics.json # Sampled metrics (JSON lines)
│   ├── events.log   # Job lifecycle events
│   └── .snapshot_state  # CPU delta calculation state
├── transport/       # Push logic
│   └── push.sh      # Push to remote storage
├── snapshot.sh      # Main orchestrator script
└── setup_cron.sh    # Cron installation helper
```

## Installation

1. **Clone or copy the monitor directory to `~/monitor`**

2. **Make scripts executable:**
   ```bash
   chmod +x ~/monitor/snapshot.sh
   chmod +x ~/monitor/collect/*.sh
   chmod +x ~/monitor/jobs/*.sh
   chmod +x ~/monitor/transport/*.sh
   chmod +x ~/monitor/setup_cron.sh
   ```

3. **Set up cron jobs:**
   ```bash
   cd ~/monitor
   ./setup_cron.sh
   ```

   Or manually add to crontab:
   ```bash
   crontab -e
   ```
   Add these lines:
   ```
   * * * * * ~/monitor/snapshot.sh
   * * * * * sleep 15 && ~/monitor/snapshot.sh
   * * * * * sleep 30 && ~/monitor/snapshot.sh
   * * * * * sleep 45 && ~/monitor/snapshot.sh
   ```

## Usage

### Metric Collection

Metrics are automatically collected every 15 seconds and appended to `~/monitor/out/metrics.json`. The file automatically maintains only the last 100 entries to prevent unbounded growth and reduce I/O operations. You can change this limit by setting the `MAX_METRICS` environment variable.

**Metrics Schema:**
```json
{
  "ts": 1705180800,
  "cpu": {
    "usage_percent": 45.23,
    "load_1m": 1.25
  },
  "memory": {
    "available_mb": 8192,
    "total_mb": 16384
  },
  "thermal": {
    "cpu_temp_c": 65
  },
  "disk": {
    "read_sectors": 12345678,
    "write_sectors": 9876543
  },
  "network": {
    "rx_bytes": 1234567890,
    "tx_bytes": 9876543210
  }
}
```

### Job Logging

Wrap your jobs with the job runner to log lifecycle events:

```bash
~/monitor/jobs/run_job.sh simA ./my_simulation.sh --args
```

This will log:
```
2026-01-13 21:04 job=simA start
2026-01-13 22:17 job=simA end rc=0
```

### Web Server (for Grafana)

Expose metrics via HTTP on port 9000:

**Manual start:**
```bash
# Start the web server
python3 ~/monitor/web_server.py

# Or run in background
nohup python3 ~/monitor/web_server.py > ~/monitor/out/web_server.log 2>&1 &
```

**Auto-start on boot (recommended):**
```bash
# Install systemd service
chmod +x ~/monitor/install_service.sh
~/monitor/install_service.sh

# Enable lingering (allows user services to start on boot without login)
loginctl enable-linger $USER

# Enable and start the service
systemctl --user enable monitor-web.service
systemctl --user start monitor-web.service

# Check status
systemctl --user status monitor-web.service

# View logs
journalctl --user -u monitor-web.service -f
```

**Endpoints:**
- `http://localhost:9000/latest` - Latest metric snapshot as JSON
- `http://localhost:9000/events` - Job events log as plain text

The server sets `Cache-Control: no-cache` headers so Grafana will fetch fresh data on each request. The systemd service will automatically restart the server if it crashes and start it on boot.

### Data Transport

Push metrics to a remote storage node (e.g., Raspberry Pi):

```bash
# Set destination
export PUSH_DEST="user@raspberry-pi:/home/user/monitor-data"

# Manual push
~/monitor/transport/push.sh

# Or periodic push via cron (e.g., every hour)
0 * * * * ~/monitor/transport/push.sh
```

## Metric Sources

The system reads from standard Linux `/proc` and `/sys` filesystems:

- **CPU**: `/proc/stat` - CPU time counters
- **Load**: `/proc/loadavg` - System load average
- **Memory**: `/proc/meminfo` - Memory statistics
- **Disk**: `/proc/diskstats` - Disk I/O counters
- **Network**: `/proc/net/dev` - Network interface statistics
- **Thermal**: `/sys/class/thermal/thermal_zone*/temp` - CPU temperature

## Customization

### Change Monitor Directory

Set `MONITOR_DIR` environment variable:
```bash
export MONITOR_DIR=/custom/path/monitor
```

### Adjust Sampling Interval

Edit cron entries to change from 15 seconds to another interval. For 30 seconds:
```
* * * * * ~/monitor/snapshot.sh
* * * * * sleep 30 && ~/monitor/snapshot.sh
```

### Adjust Metrics Retention

By default, only the last 100 metric entries are kept to prevent unbounded file growth and reduce I/O operations. To change this:

```bash
export MAX_METRICS=200  # Keep last 200 entries
```

Add to `~/.bashrc` or set in cron environment for persistence.

### Add Custom Metrics

1. Create a new collector script in `collect/`
2. Modify `snapshot.sh` to call it and include in JSON output

## Requirements

- Linux system with `/proc` and `/sys` filesystems
- `bash` shell
- `bc` (for floating-point CPU calculations)
- `python3` (for web server, optional)
- `rsync` or `scp` (for transport, optional)
- `cron` (for scheduling)

## Non-Goals

This system explicitly avoids:
- Prometheus exporters
- Node exporters
- Metrics daemons
- High-cardinality labels
- Per-rank MPI logging

## Future Extensions

Potential additions (not yet implemented):
- NUMA metrics
- Page fault tracking
- MPI phase markers
- Alert thresholds
- Binary payload compression

## Troubleshooting

**Metrics not being collected:**
- Check cron jobs: `crontab -l`
- Verify scripts are executable: `ls -l ~/monitor/collect/*.sh`
- Check output directory permissions: `ls -ld ~/monitor/out`

**CPU usage always 0:**
- Ensure `bc` is installed: `which bc`
- Check state file exists: `ls -l ~/monitor/out/.snapshot_state`

**Transport fails:**
- Verify SSH access: `ssh user@host`
- Check rsync/scp availability: `which rsync scp`
- Review transport log: `tail ~/monitor/out/transport.log`

## License

This is a lightweight monitoring tool designed for HPC environments. Use and modify as needed.

