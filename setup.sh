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
sudo apt-get install -y python3-venv python3-pip libjpeg-dev zlib1g-dev i2c-tools fonts-dejavu swig liblgpio-dev

echo "========================================"
echo "Configuring Raspberry Pi Hardware..."
echo "========================================"
echo "Enabling I2C bus..."
sudo raspi-config nonint do_i2c 0

echo "Disabling Serial Login Console..."
sudo raspi-config nonint do_serial_cons 1

echo "Enabling Serial Hardware Port..."
sudo raspi-config nonint do_serial_hw 0

echo "Granting hardware permissions to $USER_NAME..."
sudo usermod -a -G i2c,dialout "$USER_NAME"

echo "========================================"
echo "Setting up application environment..."
echo "========================================"
cd "$APP_DIR"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Installing Python requirements..."
if [ -f "requirements.txt" ]; then
    .venv/bin/pip install -r requirements.txt
else
    echo "No requirements.txt found. Skipping package installation."
fi

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
sudo systemctl restart "$SERVICE_NAME" || true

echo "========================================"
echo "Setup complete! A reboot is required to apply hardware changes."
echo "========================================"
read -p "Would you like to reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    sudo reboot
fi
