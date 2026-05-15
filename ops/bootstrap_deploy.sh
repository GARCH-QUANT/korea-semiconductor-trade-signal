#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/semiconductor-deploy"
PYTHON_BIN="python3"
SERVICE_NAME="korea-semiconductor-pipeline"

sudo mkdir -p "$APP_DIR"
sudo cp -r ./* "$APP_DIR/"
sudo chown -R "$USER":"$USER" "$APP_DIR"
cd "$APP_DIR"

$PYTHON_BIN -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p logs archive data/raw data/processed reports
cp -n .env.example .env || true

sed "s|/opt/semiconductor-deploy|$APP_DIR|g; s|User=ubuntu|User=$USER|g; s|Group=ubuntu|Group=$(id -gn)|g" systemd_service.template > ${SERVICE_NAME}.service
cp systemd_timer.template ${SERVICE_NAME}.timer

sudo cp ${SERVICE_NAME}.service /etc/systemd/system/
sudo cp ${SERVICE_NAME}.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}.timer
sudo systemctl start ${SERVICE_NAME}.timer

echo "Deployment completed. Edit $APP_DIR/.env before first live run."
