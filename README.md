# Server Analytics

Live analytics from a home server, with a Raspberry Pi acting as a heartbeat sensor. Metrics are collected on the server, exposed over HTTP, and consumed over a VPN by a Grafana dashboard running on the Pi.

## Overview

This project provides:

- **Lightweight monitoring** on the server (no Prometheus/Node Exporter, no daemons)
- **Metrics collection** every 15 seconds (CPU, memory, thermal, disk I/O, network)
- **HTTP API** on port 9000 for the latest snapshot
- **Raspberry Pi dashboard** that polls the server over VPN, computes derived rates, and serves Grafana-ready JSON
- **Grafana** for visualization (CPU usage, load, memory, temperature, disk/network rates)

Design goals: minimal footprint, full user control, HPC-friendly, no UI dependencies on the server side.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HOME SERVER (e.g. Precision Tower)                                         │
│  ┌─────────────┐    cron every 15s    ┌──────────────┐                      │
│  │ snapshot.sh │ ──────────────────►  │ metrics.json │                      │
│  │ (collectors)│                      │ (last 100)   │                      │
│  └─────────────┘                      └──────┬───────┘                      │
│                                              │                              │
│  ┌───────────────────────────────────────────▼─────────────────────────────┐│
│  │ web_server.py (port 9000)                                               ││
│  │ GET /latest  → latest metric JSON   GET /events → job events log        ││
│  └──────────────────────────────────────────┬──────────────────────────────┘│
└─────────────────────────────────────────────┼───────────────────────────────┘
                                              │
                                    VPN / network
                                              │
┌─────────────────────────────────────────────▼───────────────────────────────┐
│  RASPBERRY PI                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ dashboard_server.py (port 9100)                                       │  │
│  │ Polls server:9000/latest → in-memory → derived rates                  │  │
│  │ GET /metrics → JSON for Grafana   GET /health → ok|stale              │  │
│  │ GET / → built-in HTML dashboard                                       │  │
│  └─────────────────────────────────────────┬─────────────────────────────┘  │
│                                            │                                │
│  ┌─────────────────────────────────────────▼─────────────────────────────┐  │
│  │ Grafana (JSON datasource) → dashboards                                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| **monitor/** | Server-side: metric collectors (shell scripts), snapshot orchestrator, web server on port 9000, job logging, optional push/transport. See [monitor/README.md](monitor/README.md). |
| **graphana-dashboard/** | Pi-side: Python service that polls the server, computes rates, exposes JSON and a simple dashboard. See [graphana-dashboard/README.md](graphana-dashboard/README.md). |

## Quick Start

### 1. On the home server

```bash
# Copy monitor to e.g. ~/monitor
cp -r monitor ~/monitor
cd ~/monitor

# Make scripts executable
chmod +x snapshot.sh collect/*.sh jobs/*.sh transport/*.sh setup_cron.sh install_service.sh

# Set up cron (metrics every 15s)
./setup_cron.sh

# Optional: run web server as user service (port 9000)
./install_service.sh
loginctl enable-linger $USER
systemctl --user enable monitor-web.service
systemctl --user start monitor-web.service
```

Ensure the server is reachable from the Pi (VPN or LAN) at `http://<server-ip>:9000/latest`.

### 2. On the Raspberry Pi

```bash
# Copy graphana-dashboard to the Pi
scp -r graphana-dashboard pi@<pi-ip>:~/

# On the Pi
cd ~/graphana-dashboard
chmod +x install_service.sh
./install_service.sh

# Configure metrics URL to point to your server (e.g. over VPN)
# Edit config or: python3 dashboard_server.py --metrics-endpoint http://<server-ip>:9000/latest

# Run as system service
sudo systemctl enable pi-grafana-dashboard
sudo systemctl start pi-grafana-dashboard
```

Then point Grafana’s JSON datasource at `http://127.0.0.1:9100/metrics` (or the Pi’s IP if Grafana runs elsewhere).

## Metrics

- **Server** collects: CPU usage %, load (1m), memory (available/total MB), CPU temperature (°C), disk read/write sectors, network RX/TX bytes.
- **Dashboard** adds: disk read/write *rates*, network RX/TX *rates* (from counter deltas).

## Requirements

- **Server**: Linux with `/proc` and `/sys`, bash, awk, Python 3, cron.
- **Raspberry Pi**: Python 3.9+, network access to server, ~60MB RAM for the dashboard service.

## License

MIT. See [LICENSE](LICENSE).

## Links

- **Monitor (server)**: [monitor/README.md](monitor/README.md) — installation, cron, web server, job wrapper, transport.
- **Grafana dashboard (Pi)**: [graphana-dashboard/README.md](graphana-dashboard/README.md) — installation, endpoints, Grafana setup.
