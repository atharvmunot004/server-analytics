# Quick Start Guide

## 1. Installation

```bash
# Copy monitor directory to home
cp -r monitor ~/monitor

# Make scripts executable
chmod +x ~/monitor/snapshot.sh
chmod +x ~/monitor/collect/*.sh
chmod +x ~/monitor/jobs/*.sh
chmod +x ~/monitor/transport/*.sh
chmod +x ~/monitor/setup_cron.sh
chmod +x ~/monitor/test_collectors.sh
```

## 2. Test Collectors

```bash
cd ~/monitor
./test_collectors.sh
```

## 3. Run Manual Snapshot

```bash
cd ~/monitor
./snapshot.sh
cat out/metrics.json
```

## 4. Setup Automatic Collection

```bash
cd ~/monitor
./setup_cron.sh
```

Verify cron jobs:
```bash
crontab -l
```

## 5. Test Job Wrapper

```bash
# Run a test job
~/monitor/jobs/run_job.sh test_job sleep 5

# Check events log
cat ~/monitor/out/events.log
```

## 6. Start Web Server (for Grafana)

**Option A: Manual start**
```bash
# Start HTTP server on port 9000
python3 ~/monitor/web_server.py

# Or run in background
nohup python3 ~/monitor/web_server.py > ~/monitor/out/web_server.log 2>&1 &
```

**Option B: Auto-start on boot (recommended)**
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
```

Access endpoints:
- `http://localhost:9000/latest` - Latest metric (JSON)
- `http://localhost:9000/events` - Events log (text)

## 7. Configure Remote Push (Optional)

```bash
# Set destination
export PUSH_DEST="user@raspberry-pi:/home/user/monitor-data"

# Test push
~/monitor/transport/push.sh

# Add to cron for periodic push (e.g., every hour)
crontab -e
# Add: 0 * * * * ~/monitor/transport/push.sh
```

## Verification

Check that metrics are being collected:
```bash
# View latest metrics
tail -n 5 ~/monitor/out/metrics.json | python3 -m json.tool

# Check file size (should grow over time)
ls -lh ~/monitor/out/metrics.json
```

## Troubleshooting

**No metrics appearing:**
- Check cron: `crontab -l`
- Check permissions: `ls -l ~/monitor/collect/*.sh`
- Run manually: `~/monitor/snapshot.sh`

**CPU usage always 0:**
- First run will be 0 (no previous state)
- Wait for second run (15 seconds later)
- Check state file: `cat ~/monitor/out/.snapshot_state`

**Collectors fail:**
- Ensure running on Linux with `/proc` filesystem
- Check script permissions: `ls -l ~/monitor/collect/`
- Test individually: `~/monitor/collect/cpu.sh`

