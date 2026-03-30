#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

echo "== Youth Together deployment check =="
echo "repo_root=$REPO_ROOT"
echo

echo "== systemd timers =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl status youth-together-pipeline.timer --no-pager || true
  echo
  systemctl status youth-together-backup.timer --no-pager || true
else
  echo "systemctl not available"
fi

echo
echo "== nginx =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl status nginx --no-pager || true
else
  echo "systemctl not available"
fi

echo
echo "== latest pipeline status =="
if [[ -f "$REPO_ROOT/output/pipeline_status.json" ]]; then
  python3 - <<'PY' "$REPO_ROOT/output/pipeline_status.json"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8-sig"))
for key in [
    "status",
    "started_at",
    "finished_at",
    "article_date_basis",
    "freshness_target",
    "schedule",
]:
    if key in payload:
        print(f"{key}={payload[key]}")
PY
else
  echo "pipeline_status.json not found"
fi

echo
echo "== latest logs =="
if [[ -d "$REPO_ROOT/output/scheduler_logs" ]]; then
  find "$REPO_ROOT/output/scheduler_logs" -type f | sort | tail -n 5
else
  echo "scheduler_logs directory not found"
fi
