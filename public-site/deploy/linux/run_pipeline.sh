#!/usr/bin/env bash
set -euo pipefail

PUBLIC_SITE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(cd "$PUBLIC_SITE_ROOT/.." && pwd)"
LOG_DIR="$REPO_ROOT/runtime/logs/scheduler_logs"
LOCK_FILE="$REPO_ROOT/runtime/pipeline/pipeline.lock"
mkdir -p "$LOG_DIR"

export TZ="Asia/Seoul"

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PATH="$LOG_DIR/linux_run_${TIMESTAMP}.log"

{
  echo "[$(date --iso-8601=seconds)] scheduled_run_started"
  echo "repo_root=$REPO_ROOT"
  echo "public_site_root=$PUBLIC_SITE_ROOT"
  echo "python_bin=$PYTHON_BIN"
  echo "log_path=$LOG_PATH"

  if [[ -f "$LOCK_FILE" ]]; then
    echo "pipeline_lock_detected=$LOCK_FILE"
  fi

  "$PYTHON_BIN" "$PUBLIC_SITE_ROOT/scripts/cron_runner.py"
  echo "[$(date --iso-8601=seconds)] scheduled_run_finished exit_code=0"
} >>"$LOG_PATH" 2>&1
