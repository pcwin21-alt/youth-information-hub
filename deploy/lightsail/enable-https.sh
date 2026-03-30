#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:?DOMAIN must be set}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:?CERTBOT_EMAIL must be set}"

sudo apt update
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx \
  --non-interactive \
  --agree-tos \
  --redirect \
  -m "$CERTBOT_EMAIL" \
  -d "$DOMAIN"

echo "[https] enabled for $DOMAIN"
echo "[https] certbot timer status:"
systemctl status certbot.timer --no-pager || true
