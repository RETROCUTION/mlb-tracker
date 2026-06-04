#!/usr/bin/env bash
set -euo pipefail

APP_NAME="MLB Tracker"
SERVICE_NAME="mlb-tracker"
REPO_ZIP_URL="https://github.com/RETROCUTION/mlb-tracker/archive/refs/heads/main.zip"
USE_LOCAL_SOURCE="${MLB_TRACKER_UPDATE_LOCAL:-0}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this updater with sudo:"
  echo "  sudo ./update.sh"
  echo
  echo "Or use:"
  echo "  curl -fsSL https://raw.githubusercontent.com/RETROCUTION/mlb-tracker/main/update.sh | sudo bash"
  exit 1
fi

detect_install_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER:-}" != "root" ]]; then
    echo "$SUDO_USER"
    return
  fi

  local service_user
  service_user="$(systemctl cat "$SERVICE_NAME.service" 2>/dev/null | awk -F= '/^User=/{print $2; exit}' || true)"
  if [[ -n "$service_user" ]]; then
    echo "$service_user"
    return
  fi

  if getent passwd pi >/dev/null 2>&1; then
    echo "pi"
    return
  fi

  echo "Could not determine install user." >&2
  echo "Run the full installer first, or run this through sudo from the target user." >&2
  exit 1
}

INSTALL_USER="$(detect_install_user)"
INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
if [[ -z "$INSTALL_HOME" ]]; then
  echo "Could not determine home directory for $INSTALL_USER"
  exit 1
fi

APP_DIR="$INSTALL_HOME/mlb-tracker"
if [[ ! -d "$APP_DIR" ]]; then
  echo "$APP_DIR does not exist."
  echo "Run the full installer first:"
  echo "  sudo ./install.sh"
  exit 1
fi

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" >/dev/null 2>&1 && pwd || pwd)"
SRC_DIR="$PACKAGE_DIR/mlb-tracker"
TMP_DIR=""

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

if [[ "$USE_LOCAL_SOURCE" == "1" && -d "$SRC_DIR" && "$SRC_DIR" != "$APP_DIR" && -f "$PACKAGE_DIR/install.sh" ]]; then
  echo "Using local installer package source."
else
  for cmd in curl unzip rsync; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      echo "Missing required command: $cmd"
      echo "Run the full installer once, then try the quick updater again."
      exit 1
    fi
  done

  TMP_DIR="$(mktemp -d)"
  echo "Downloading latest $APP_NAME files from GitHub..."
  curl -fsSL -o "$TMP_DIR/mlb-tracker-main.zip" "$REPO_ZIP_URL"
  unzip -q "$TMP_DIR/mlb-tracker-main.zip" -d "$TMP_DIR"
  SRC_DIR="$TMP_DIR/mlb-tracker-main/mlb-tracker"
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Could not find source folder: $SRC_DIR"
  exit 1
fi

echo "Fast-updating $APP_NAME for user $INSTALL_USER"
echo "Install directory: $APP_DIR"

systemctl stop "$SERVICE_NAME.service" >/dev/null 2>&1 || true

rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'settings.json' \
  --exclude 'cache/' \
  --exclude 'output/' \
  --exclude 'mlb_tracker.log' \
  "$SRC_DIR/" "$APP_DIR/"

install -d -o "$INSTALL_USER" -g "$INSTALL_USER" "$APP_DIR/cache" "$APP_DIR/output"
chown -R "$INSTALL_USER:$INSTALL_USER" "$APP_DIR"
chmod +x "$APP_DIR/scripts/setup_wizard.py"

install -d /etc/systemd/system/mlb-tracker.service.d
cat > /etc/systemd/system/mlb-tracker.service.d/repair.conf <<EOF
[Service]
Environment=PYTHONFAULTHANDLER=1
ExecStartPre=/bin/sleep 20
StandardError=append:$APP_DIR/mlb-tracker.stderr.log
EOF

systemctl daemon-reload
systemctl restart "$SERVICE_NAME.service"

echo
echo "$APP_NAME quick update complete."
echo "Check status with:"
echo "  sudo systemctl status mlb-tracker --no-pager"
