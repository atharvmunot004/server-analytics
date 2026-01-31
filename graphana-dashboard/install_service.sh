#!/bin/bash
# Installation script for Raspberry Pi Stateless Grafana Dashboard systemd service

set -e

echo "Raspberry Pi Stateless Grafana Dashboard - Service Installation"
echo "================================================================"

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DASHBOARD_DIR="$HOME/graphana-dashboard"
SERVICE_FILE="pi-grafana-dashboard.service"

# Check if running as root for service installation
if [ "$EUID" -eq 0 ]; then 
   echo "Error: Don't run this script as root. It will ask for sudo when needed."
   exit 1
fi

# Get username
USERNAME=$(whoami)
PYTHON_PATH=$(which python3)

if [ -z "$PYTHON_PATH" ]; then
    echo "Error: python3 not found in PATH"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Username: $USERNAME"
echo "  Python: $PYTHON_PATH"
echo "  Dashboard directory: $DASHBOARD_DIR"
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$DASHBOARD_DIR"

# Copy files
echo "Copying files..."
cp "$SCRIPT_DIR/dashboard_server.py" "$DASHBOARD_DIR/"
cp "$SCRIPT_DIR/config.json" "$DASHBOARD_DIR/"

# Make script executable
chmod +x "$DASHBOARD_DIR/dashboard_server.py"

# Create service file with correct paths
echo "Creating systemd service file..."
cat > /tmp/pi-grafana-dashboard.service << EOF
[Unit]
Description=Raspberry Pi Stateless Grafana Dashboard
Documentation=https://github.com/your-repo/grafana-dashboard
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USERNAME
Group=$USERNAME
WorkingDirectory=$DASHBOARD_DIR
ExecStart=$PYTHON_PATH $DASHBOARD_DIR/dashboard_server.py --bind 0.0.0.0 --port 9100 --metrics-endpoint http://100.67.229.89:9000/latest --poll-interval 15 --timeout 10 --max-age 30
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pi-grafana-dashboard

# Resource limits
MemoryMax=60M
CPUQuota=25%

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Install service file
echo "Installing systemd service..."
sudo cp /tmp/pi-grafana-dashboard.service /etc/systemd/system/pi-grafana-dashboard.service
rm /tmp/pi-grafana-dashboard.service

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable service
echo "Enabling service to start on boot..."
sudo systemctl enable pi-grafana-dashboard.service

# Ask if user wants to start now
read -p "Start the service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting service..."
    sudo systemctl start pi-grafana-dashboard.service
    sleep 2
    sudo systemctl status pi-grafana-dashboard.service --no-pager
    echo ""
    echo "Service started! View logs with: sudo journalctl -u pi-grafana-dashboard.service -f"
else
    echo "Service installed but not started. Start it with: sudo systemctl start pi-grafana-dashboard.service"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Useful commands:"
echo "  Check status:  sudo systemctl status pi-grafana-dashboard.service"
echo "  View logs:     sudo journalctl -u pi-grafana-dashboard.service -f"
echo "  Stop service:  sudo systemctl stop pi-grafana-dashboard.service"
echo "  Start service: sudo systemctl start pi-grafana-dashboard.service"
echo "  Restart:       sudo systemctl restart pi-grafana-dashboard.service"
echo ""
echo "Dashboard available at: http://127.0.0.1:9100"
echo "Metrics endpoint: http://127.0.0.1:9100/metrics"
echo "Health endpoint: http://127.0.0.1:9100/health"
