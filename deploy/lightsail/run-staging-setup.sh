#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${CONFIG_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/staging-config.env}"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "config file not found: $CONFIG_PATH" >&2
  echo "copy deploy/lightsail/staging-config.env.example to deploy/lightsail/staging-config.env first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_PATH"

: "${REPO_URL:?REPO_URL must be set in $CONFIG_PATH}"
: "${DOMAIN:?DOMAIN must be set in $CONFIG_PATH}"

export APP_NAME="${APP_NAME:-youth-together}"
export APP_USER="${APP_USER:-youthtogether}"
export APP_GROUP="${APP_GROUP:-youthtogether}"
export APP_DIR="${APP_DIR:-/opt/youth-together}"
export REPO_URL
export REPO_REF="${REPO_REF:-main}"
export DOMAIN
export ENV_FILE="${ENV_FILE:-/etc/youth-together.env}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$SCRIPT_DIR/bootstrap-staging.sh"

if [[ "${ENABLE_HTTPS:-0}" == "1" ]]; then
  : "${CERTBOT_EMAIL:?CERTBOT_EMAIL must be set in $CONFIG_PATH when ENABLE_HTTPS=1}"
  export CERTBOT_EMAIL
  bash "$SCRIPT_DIR/enable-https.sh"
else
  echo "[staging-setup] ENABLE_HTTPS is not 1, skipping HTTPS step"
fi
