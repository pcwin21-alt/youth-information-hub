#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
REPO_REF="${REPO_REF:-main}"
RUN_PIPELINE_AFTER_UPDATE="${RUN_PIPELINE_AFTER_UPDATE:-0}"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "git repository not found at $REPO_ROOT" >&2
  exit 1
fi

if [[ ! -d "$REPO_ROOT/.venv" ]]; then
  python3 -m venv "$REPO_ROOT/.venv"
fi

# shellcheck disable=SC1091
source "$REPO_ROOT/.venv/bin/activate"

cd "$REPO_ROOT"
git fetch --all --tags
git checkout "$REPO_REF"
git pull --ff-only origin "$REPO_REF"
pip install --upgrade pip
pip install -e "$REPO_ROOT"

if [[ "$RUN_PIPELINE_AFTER_UPDATE" == "1" ]]; then
  "$REPO_ROOT/deploy/linux/run_pipeline.sh"
fi

echo "update_completed repo_ref=$REPO_REF run_pipeline_after_update=$RUN_PIPELINE_AFTER_UPDATE"
