#!/usr/bin/env bash
set -euo pipefail

APP_NAME="MLB Tracker"
SERVICE_NAME="mlb-tracker"
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$PACKAGE_DIR/mlb-tracker"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this installer with sudo:"
  echo "  sudo ./install.sh"
  exit 1
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Could not find package source folder: $SRC_DIR"
  echo "Make sure you run install.sh from the unzipped MLB Tracker package."
  exit 1
fi

INSTALL_USER="${SUDO_USER:-pi}"
INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
if [[ -z "$INSTALL_HOME" ]]; then
  echo "Could not determine home directory for $INSTALL_USER"
  exit 1
fi

APP_DIR="$INSTALL_HOME/mlb-tracker"
EPAPER_DIR="$INSTALL_HOME/e-Paper"

internet_ok() {
  /usr/bin/python3 - <<'PY'
import socket
try:
    socket.create_connection(("statsapi.mlb.com", 443), timeout=5).close()
    raise SystemExit(0)
except OSError:
    raise SystemExit(1)
PY
}

echo "Installing $APP_NAME for user $INSTALL_USER"
echo "Install directory: $APP_DIR"

if ! internet_ok; then
  if [[ -t 0 ]]; then
    echo "No internet connection detected. Starting Wi-Fi setup first."
    /usr/bin/python3 "$SRC_DIR/scripts/setup_wizard.py" --wifi-only
  else
    echo "No internet connection detected and no interactive terminal is attached."
    echo "Configure Wi-Fi with Raspberry Pi Imager or connect keyboard/HDMI and retry."
    exit 1
  fi
fi

echo "Installing system packages..."
apt-get update
apt-get install -y \
  git \
  rsync \
  python3 \
  python3-pil \
  python3-requests \
  python3-gpiozero \
  python3-spidev \
  python3-rpi.gpio \
  network-manager \
  wireless-tools

if command -v raspi-config >/dev/null 2>&1; then
  echo "Enabling SPI..."
  raspi-config nonint do_spi 0 || true
fi

if [[ ! -d "$EPAPER_DIR/RaspberryPi_JetsonNano/python/lib/waveshare_epd" ]]; then
  echo "Installing Waveshare e-Paper Python driver..."
  if [[ -d "$EPAPER_DIR" ]]; then
    mv "$EPAPER_DIR" "$EPAPER_DIR.backup.$(date +%Y%m%d%H%M%S)"
  fi
  sudo -u "$INSTALL_USER" git clone --depth 1 \
    https://github.com/waveshareteam/e-Paper.git "$EPAPER_DIR"
else
  echo "Waveshare e-Paper driver already present."
fi

echo "Copying application files..."
install -d -o "$INSTALL_USER" -g "$INSTALL_USER" "$APP_DIR"
rsync -a \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'settings.json' \
  --exclude 'cache/*.json' \
  --exclude 'output/*' \
  "$SRC_DIR/" "$APP_DIR/"

install -d -o "$INSTALL_USER" -g "$INSTALL_USER" "$APP_DIR/cache" "$APP_DIR/output"
chown -R "$INSTALL_USER:$INSTALL_USER" "$APP_DIR"
chmod +x "$APP_DIR/scripts/setup_wizard.py"

echo "Installing systemd services..."
cat > /etc/systemd/system/mlb-tracker.service <<EOF
[Unit]
Description=MLB Tracker
After=network-online.target
Wants=network-online.target
ConditionPathExists=$APP_DIR/settings.json

[Service]
Type=simple
User=$INSTALL_USER
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 $APP_DIR/main.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/mlb-tracker-setup.service <<EOF
[Unit]
Description=MLB Tracker first-run setup
After=multi-user.target
Before=mlb-tracker.service
ConditionPathExists=!$APP_DIR/settings.json

[Service]
Type=oneshot
Environment=MLB_TRACKER_USER=$INSTALL_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/scripts/setup_wizard.py --first-boot
StandardInput=tty-force
StandardOutput=tty
StandardError=tty
TTYPath=/dev/tty1
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

if [[ -f "$APP_DIR/settings.json" ]]; then
  echo "Existing settings found. Enabling MLB Tracker service."
  systemctl disable mlb-tracker-setup.service >/dev/null 2>&1 || true
  systemctl enable mlb-tracker.service
  systemctl restart mlb-tracker.service
else
  echo "No team settings found."
  if [[ -t 0 ]]; then
    echo "Starting setup wizard now."
    MLB_TRACKER_USER="$INSTALL_USER" /usr/bin/python3 "$APP_DIR/scripts/setup_wizard.py"
    systemctl disable mlb-tracker-setup.service >/dev/null 2>&1 || true
    systemctl enable mlb-tracker.service
    systemctl restart mlb-tracker.service
  else
    echo "Enabling first-run setup on the Pi console."
    echo "On next boot, connect a keyboard/display and complete MLB Tracker setup."
    systemctl disable mlb-tracker.service >/dev/null 2>&1 || true
    systemctl enable mlb-tracker-setup.service
  fi
fi

echo
echo "$APP_NAME install complete."
echo "Useful commands:"
echo "  sudo systemctl status mlb-tracker --no-pager"
echo "  journalctl -u mlb-tracker -n 150 --no-pager -l"
echo "  python3 $APP_DIR/scripts/setup_wizard.py --force"
