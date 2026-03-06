#!/bin/bash

set -e

if [ "$EUID" -eq 0 ] && [ "$1" != "--allow-root" ]; then
  echo "Error: Please do not run this script as root or with sudo."
  echo "Run it as your normal user. It will prompt for your password when needed."
  echo "If you absolutely must run as root, use: ./setup.sh --allow-root"
  exit 1
fi

USER_NAME=$(whoami)
USER_GROUP=$(id -gn "$USER_NAME")
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SERVICE_NAME="momir-basic-printer.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "========================================"
echo "Updating system and checking packages..."
echo "========================================"
sudo apt-get update -qq
sudo apt-get install -y python3-venv python3-pip libjpeg-dev zlib1g-dev

echo "========================================"
echo "Setting up application environment..."
echo "========================================"
cd "$APP_DIR"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Installing Python requirements..."
.venv/bin/pip install -r requirements.txt

echo "========================================"
echo "Configuring systemd service..."
echo "========================================"
sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=Momir Basic Printer Service
After=network.target

[Service]
User=$USER_NAME
Group=$USER_GROUP
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python src/main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling $SERVICE_NAME to start on boot..."
sudo systemctl enable "$SERVICE_NAME"

echo "Restarting $SERVICE_NAME to apply any changes..."
sudo systemctl restart "$SERVICE_NAME"

echo "========================================"
echo "Setup complete! Current service status:"
echo "========================================"
sudo systemctl status "$SERVICE_NAME" --no-pager
