# Raspberry Pi Stateless Grafana Dashboard

A **fully stateless, lightweight** metrics adapter for Raspberry Pi that polls upstream metrics, calculates derived rates, and exposes them via HTTP endpoints for Grafana consumption. The dashboard is completely in-memory with no disk I/O, no persistence, and bounded memory usage.

## Features

- ✅ **Fully Stateless** - No disk I/O, no file reads/writes, in-memory only
- ✅ **No Persistence** - All state resets on restart (crash-safe, reboot-safe)
- ✅ **Bounded Memory** - Single latest sample only, no accumulation
- ✅ **Derived Metrics** - Automatic rate calculation from counters (disk I/O, network)
- ✅ **Staleness Detection** - Monitors timestamp advancement and data freshness
- ✅ **Lightweight** - ~60MB memory budget, 25% CPU budget
- ✅ **Grafana Ready** - JSON HTTP endpoints compatible with Grafana JSON datasource
- ✅ **Web Dashboard** - Built-in HTML dashboard with gray background and light colored graphs

## Architecture

```
External Metrics Endpoint → Dashboard Server (127.0.0.1:9100) → Grafana / Browser
  http://100.67.229.89:9000/metrics    In-Memory Processing      JSON HTTP
```

- **Metrics Source**: External server exposes metrics at `http://100.67.229.89:9000/metrics` (JSON)
- **Dashboard Server**: Runs on Raspberry Pi at `127.0.0.1:9100`, processes metrics in-memory
- **Endpoints**:
  - `/` - HTML dashboard
  - `/metrics` - Latest sample with derived metrics (JSON object)
  - `/health` - Health status (ok/stale) and last seen timestamp

## Requirements

- Python 3.9.2 or higher
- Network access to the metrics endpoint
- ~60MB RAM available
- Raspberry Pi 3 or compatible

## Installation

1. **Transfer files to Raspberry Pi:**
   ```bash
   scp -r . pi@<raspberry-pi-ip>:~/graphana-dashboard/
   ```

2. **SSH into Raspberry Pi:**
   ```bash
   ssh pi@<raspberry-pi-ip>
   cd ~/graphana-dashboard
   ```

3. **Run installation script:**
   ```bash
   chmod +x install_service.sh
   ./install_service.sh
   ```

## Usage

### Manual Start

```bash
python3 dashboard_server.py
```

Dashboard available at `http://127.0.0.1:9100`

### Custom Configuration

```bash
# Custom port
python3 dashboard_server.py --port 8080

# Custom bind address
python3 dashboard_server.py --bind 0.0.0.0

# Custom metrics endpoint
python3 dashboard_server.py --metrics-endpoint http://192.168.1.100:9000/metrics

# Custom poll interval
python3 dashboard_server.py --poll-interval 10

# Custom staleness threshold
python3 dashboard_server.py --max-age 60
```

### Service Management

```bash
# Start service
sudo systemctl start pi-grafana-dashboard

# Stop service
sudo systemctl stop pi-grafana-dashboard

# Check status
sudo systemctl status pi-grafana-dashboard

# View logs
sudo journalctl -u pi-grafana-dashboard -f

# Enable auto-start on boot
sudo systemctl enable pi-grafana-dashboard
```

## Dashboard Features

The dashboard displays:

- **CPU Usage %**: Usage percentage with time-series chart
- **CPU Load (1m)**: 1-minute load average with chart
- **Available Memory**: Available memory in MB with chart
- **CPU Temperature**: CPU temperature in Celsius with chart
- **Disk Read / Write Rate**: Derived rates from counter deltas (sectors/sec)
- **Network RX / TX**: Derived rates from counter deltas (bytes/sec)

All metrics update automatically every 15 seconds. Rate calculations are computed server-side using time deltas between samples.

## API Endpoints

### GET /metrics

Returns the latest sample with derived metrics as a JSON object.

**Response:**
```json
{
  "ts": 1234567890,
  "cpu": {
    "usage_percent": 45.2,
    "load_1m": 1.5
  },
  "memory": {
    "available_mb": 512,
    "total_mb": 1024
  },
  "thermal": {
    "cpu_temp_c": 55.3
  },
  "disk": {
    "read_sectors": 123456,
    "write_sectors": 78901,
    "read_sectors_rate": 10.5,
    "write_sectors_rate": 2.3
  },
  "network": {
    "rx_bytes": 987654321,
    "tx_bytes": 123456789,
    "rx_bytes_rate": 1024.5,
    "tx_bytes_rate": 512.3
  }
}
```

### GET /health

Returns health status based on staleness detection.

**Response:**
```json
{
  "status": "ok",
  "last_seen_ts": 1234567890
}
```

Status values:
- `"ok"`: Data is fresh (age < 30 seconds)
- `"stale"`: Data is stale (age >= 30 seconds or no data)

## Technical Details

### Stateless Design

- **No disk I/O**: All processing in memory
- **No file reads/writes**: Completely stateless
- **No persistence**: State resets on restart
- **Single sample**: Only latest sample kept in memory
- **Bounded memory**: Fixed memory footprint (~60MB)

### Derived Metrics

Rates are calculated from counter deltas:
- Compares current counter value with previous value
- Calculates delta over time difference
- First sample shows zero rates (no previous data)
- Rates reset on restart (no persistence)

### Staleness Handling

- **Timestamp advancement**: Rejects samples with non-advancing timestamps
- **Max age**: Marks data as stale if older than 30 seconds
- **Health endpoint**: Reports status based on staleness

### Resource Limits

- **Memory**: 60MB maximum (enforced via systemd)
- **CPU**: 25% quota (enforced via systemd)
- **Network**: ~1KB per request (15s interval)

## Grafana Integration

The `/metrics` endpoint is compatible with Grafana's JSON HTTP datasource:

1. **Add JSON Datasource** in Grafana:
   - Type: JSON API
   - URL: `http://127.0.0.1:9100/metrics`
   - Access: Server (default)

2. **Configure Query**:
   - Method: GET
   - Time field: `ts` (Unix epoch seconds)

3. **Create Panels**:
   - Use JSONPath to extract fields (e.g., `$.cpu.usage_percent`)
   - Configure units and thresholds as needed

## Troubleshooting

### Dashboard shows "Stale" status

- Check metrics endpoint is accessible: `curl http://100.67.229.89:9000/metrics`
- Check service logs: `sudo journalctl -u pi-grafana-dashboard -f`
- Verify service is running: `sudo systemctl status pi-grafana-dashboard`
- Check network connectivity to metrics endpoint

### Health endpoint returns stale

- Verify upstream metrics endpoint is responding
- Check if timestamps are advancing in upstream data
- Verify poll interval is appropriate (default: 15s)
- Check max age threshold (default: 30s)

### High memory usage

- Should be ~60MB, check with: `ps aux | grep dashboard_server`
- Restart service if memory grows: `sudo systemctl restart pi-grafana-dashboard`
- Verify no file I/O is occurring (should be zero)

### Rates showing zero

- First sample after restart will show zero rates (expected)
- Verify counters are incrementing in upstream data
- Check that time deltas are positive between samples

## File Structure

```
.
├── dashboard_server.py          # Main server (stateless, in-memory)
├── pi-grafana-dashboard.service # Systemd service file
├── install_service.sh           # Installation script
├── config.json                  # Configuration specification
├── requirements.txt             # Python dependencies (none - stdlib only)
└── README.md                    # This file
```

## Configuration

See `config.json` for the complete configuration specification. Key settings:

- **Metrics Source**: Endpoint URL, poll interval, timeout
- **Internal Processing**: State model, derived metrics, staleness handling
- **Export Interface**: Bind address, port, endpoints
- **Systemd Service**: Resource limits, restart policy

## Guarantees

- ✅ **Crash Safe**: No data loss on crash (no persistence)
- ✅ **Reboot Safe**: Clean state on restart
- ✅ **Bounded Memory**: Fixed memory footprint
- ✅ **No SD Card Wear**: Zero disk I/O

## Non-Goals

- ❌ No CSV output
- ❌ No SQL database
- ❌ No Prometheus exporter
- ❌ No long-term storage
- ❌ No file rotation
- ❌ No background threads (minimal polling thread only)

## License

This project is provided as-is for personal use.
