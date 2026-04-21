#!/usr/bin/env bash
set -euo pipefail

PUBLIC_SITE_ROOT="${PUBLIC_SITE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$PUBLIC_SITE_ROOT/.." && pwd)}"

echo "== Youth Together deployment check =="
echo "repo_root=$REPO_ROOT"
echo "public_site_root=$PUBLIC_SITE_ROOT"
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
if [[ -f "$REPO_ROOT/runtime/pipeline/pipeline_status.json" ]]; then
  python3 - <<'PY' "$REPO_ROOT/runtime/pipeline/pipeline_status.json"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8-sig"))
print(f"state={payload.get('state')}")
print(f"started_at={payload.get('started_at')}")
print(f"finished_at={payload.get('finished_at')}")
date_basis = payload.get("date_basis") or {}
update_policy = payload.get("update_policy") or {}
if date_basis:
    print(f"article_date_basis={date_basis.get('article_date_basis')}")
    print(f"freshness_target_hours={date_basis.get('freshness_target_hours')}")
if update_policy:
    print(f"update_frequency={update_policy.get('frequency')}")
    print(f"update_times={','.join(update_policy.get('times', []))}")
PY
else
  echo "pipeline_status.json not found"
fi

echo
echo "== latest logs =="
if [[ -d "$REPO_ROOT/runtime/logs/scheduler_logs" ]]; then
  find "$REPO_ROOT/runtime/logs/scheduler_logs" -type f | sort | tail -n 5
else
  echo "scheduler_logs directory not found"
fi
