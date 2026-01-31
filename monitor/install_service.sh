#!/bin/bash
# install_service.sh - Install systemd service for web server auto-start

MONITOR_DIR="${MONITOR_DIR:-$HOME/monitor}"
SERVICE_FILE="$MONITOR_DIR/monitor-web.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

# Check if running as root (shouldn't be for user service)
if [ "$EUID" -eq 0 ]; then
    echo "Error: Don't run this as root. This installs a user service." >&2
    exit 1
fi

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_USER_DIR"

# Replace %i and %h placeholders with actual values
USERNAME=$(whoami)
HOME_DIR="$HOME"

# Create service file with actual paths
sed -e "s|%i|$USERNAME|g" -e "s|%h|$HOME_DIR|g" "$SERVICE_FILE" > "$SYSTEMD_USER_DIR/monitor-web.service"

echo "Service file installed to: $SYSTEMD_USER_DIR/monitor-web.service"
echo ""
echo "IMPORTANT: Enable lingering for user services to start on boot without login:"
echo "  loginctl enable-linger $USERNAME"
echo ""
echo "To enable and start the service:"
echo "  systemctl --user enable monitor-web.service"
echo "  systemctl --user start monitor-web.service"
echo ""
echo "To check status:"
echo "  systemctl --user status monitor-web.service"
echo ""
echo "To view logs:"
echo "  journalctl --user -u monitor-web.service -f"
echo ""
echo "To disable:"
echo "  systemctl --user disable monitor-web.service"
echo "  systemctl --user stop monitor-web.service"

