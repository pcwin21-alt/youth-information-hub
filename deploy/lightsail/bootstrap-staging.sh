#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-youth-together}"
APP_USER="${APP_USER:-youthtogether}"
APP_GROUP="${APP_GROUP:-youthtogether}"
APP_DIR="${APP_DIR:-/opt/youth-together}"
REPO_URL="${REPO_URL:?REPO_URL must be set}"
REPO_REF="${REPO_REF:-main}"
DOMAIN="${DOMAIN:-_}"
ENV_FILE="${ENV_FILE:-/etc/youth-together.env}"

echo "[bootstrap] start"
echo "[bootstrap] APP_DIR=$APP_DIR"
echo "[bootstrap] REPO_URL=$REPO_URL"
echo "[bootstrap] REPO_REF=$REPO_REF"

sudo timedatectl set-timezone Asia/Seoul

sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  sudo adduser --system --group --home "$APP_DIR" "$APP_USER"
fi

sudo mkdir -p "$APP_DIR"
sudo chown -R "$APP_USER":"$APP_GROUP" "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
sudo -u "$APP_USER" git fetch --all --tags
sudo -u "$APP_USER" git checkout "$REPO_REF"
sudo -u "$APP_USER" git pull --ff-only origin "$REPO_REF"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
fi

sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

sudo touch "$ENV_FILE"
sudo chmod 600 "$ENV_FILE"

sudo chmod +x "$APP_DIR/deploy/linux/"*.sh

sudo cp "$APP_DIR/deploy/systemd/youth-together-pipeline.service" /etc/systemd/system/
sudo cp "$APP_DIR/deploy/systemd/youth-together-pipeline.timer" /etc/systemd/system/
sudo cp "$APP_DIR/deploy/systemd/youth-together-backup.service" /etc/systemd/system/
sudo cp "$APP_DIR/deploy/systemd/youth-together-backup.timer" /etc/systemd/system/

for service_file in \
  /etc/systemd/system/youth-together-pipeline.service \
  /etc/systemd/system/youth-together-backup.service
do
  sudo sed -i "s|^User=.*|User=$APP_USER|" "$service_file"
  sudo sed -i "s|^Group=.*|Group=$APP_GROUP|" "$service_file"
  sudo sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$APP_DIR|" "$service_file"
  sudo sed -i "s|^ExecStart=.*run_pipeline.sh|ExecStart=$APP_DIR/deploy/linux/run_pipeline.sh|" "$service_file" || true
  sudo sed -i "s|^ExecStart=.*backup_state.sh|ExecStart=$APP_DIR/deploy/linux/backup_state.sh|" "$service_file" || true
done

sudo cp "$APP_DIR/deploy/nginx/youth-together.conf" /etc/nginx/sites-available/youth-together.conf
sudo sed -i "s|server_name _;|server_name $DOMAIN;|" /etc/nginx/sites-available/youth-together.conf
sudo sed -i "s|/opt/youth-together|$APP_DIR|g" /etc/nginx/sites-available/youth-together.conf

if [[ ! -L /etc/nginx/sites-enabled/youth-together.conf ]]; then
  sudo ln -s /etc/nginx/sites-available/youth-together.conf /etc/nginx/sites-enabled/youth-together.conf
fi

sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

sudo systemctl daemon-reload
sudo systemctl enable --now youth-together-pipeline.timer
sudo systemctl enable --now youth-together-backup.timer
sudo systemctl start youth-together-pipeline.service

echo "[bootstrap] done"
echo "[bootstrap] next commands:"
echo "  systemctl status youth-together-pipeline.timer"
echo "  systemctl status youth-together-pipeline.service"
echo "  systemctl status youth-together-backup.timer"
echo "  cat $APP_DIR/output/pipeline_status.json"
