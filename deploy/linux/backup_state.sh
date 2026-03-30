#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$REPO_ROOT/backups}"
BACKUP_KEEP_COUNT="${BACKUP_KEEP_COUNT:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARGET_DIR="$BACKUP_ROOT/$TIMESTAMP"

mkdir -p "$TARGET_DIR"

copy_if_exists() {
  local source_path="$1"
  local destination_path="$2"
  if [[ -e "$source_path" ]]; then
    mkdir -p "$(dirname "$destination_path")"
    cp -a "$source_path" "$destination_path"
  fi
}

copy_if_exists "$REPO_ROOT/db/articles.db" "$TARGET_DIR/db/articles.db"
copy_if_exists "$REPO_ROOT/output/pipeline_status.json" "$TARGET_DIR/output/pipeline_status.json"
copy_if_exists "$REPO_ROOT/output/step5_summarized.json" "$TARGET_DIR/output/step5_summarized.json"

if [[ -d "$REPO_ROOT/web" ]]; then
  tar -czf "$TARGET_DIR/web_snapshot.tar.gz" -C "$REPO_ROOT" web
fi

cat >"$TARGET_DIR/manifest.txt" <<EOF
created_at=$(date --iso-8601=seconds)
host=$(hostname)
repo_root=$REPO_ROOT
backup_root=$BACKUP_ROOT
EOF

mapfile -t existing_backups < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)
if (( ${#existing_backups[@]} > BACKUP_KEEP_COUNT )); then
  delete_count=$(( ${#existing_backups[@]} - BACKUP_KEEP_COUNT ))
  for old_backup in "${existing_backups[@]:0:delete_count}"; do
    rm -rf "$old_backup"
  done
fi

echo "backup_created=$TARGET_DIR"
