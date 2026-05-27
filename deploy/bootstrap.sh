#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/bot-calculator-cashpo

sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"

cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

echo "Done. Put .env into $APP_DIR/.env, then install systemd unit."
