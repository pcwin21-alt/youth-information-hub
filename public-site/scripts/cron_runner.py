from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _bootstrap import PUBLIC_SITE_ROOT, RUNTIME_DB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.status_utils import complete_run, initialize_status, update_step


def run_step(command: list[str]) -> str:
    result = subprocess.run(command, cwd=PUBLIC_SITE_ROOT, check=True, text=True, capture_output=True)
    stdout = result.stdout.strip()
    if stdout:
        print(stdout)
    return stdout


def acquire_lock(lock_path: Path, stale_after_hours: int = 6) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone()
    payload = {
        "pid": os.getpid(),
        "started_at": now.isoformat(),
        "stale_after_hours": stale_after_hours,
    }

    if lock_path.exists():
        try:
            existing = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}

        started_at = existing.get("started_at")
        try:
            started_at_dt = datetime.fromisoformat(started_at) if started_at else None
        except ValueError:
            started_at_dt = None

        if started_at_dt and now - started_at_dt < timedelta(hours=stale_after_hours):
            raise RuntimeError(
                f"pipeline_locked:started_at={started_at_dt.isoformat()} pid={existing.get('pid')}"
            )

        lock_path.unlink(missing_ok=True)

    lock_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-sample-data", action="store_true")
    parser.add_argument("--skip-collect-news", action="store_true")
    parser.add_argument("--skip-outbound-notifications", action="store_true")
    parser.add_argument("--curator-max-network-enrich", type=int)
    args = parser.parse_args()

    python = sys.executable
    status_path = RUNTIME_PIPELINE_ROOT / "pipeline_status.json"
    lock_path = RUNTIME_PIPELINE_ROOT / "pipeline.lock"
    acquire_lock(lock_path)
    initialize_status(status_path)
    collect_news = [python, str(PUBLIC_SITE_ROOT / "scripts" / "rss_fetcher.py")]
    collect_youtube = [python, str(PUBLIC_SITE_ROOT / "scripts" / "youtube_fetcher.py")]
    if args.use_sample_data:
        collect_news.append("--use-sample-data")
        collect_news.append("--fallback-to-sample")
        collect_youtube.append("--use-sample-data")
    curator_command = [python, str(PUBLIC_SITE_ROOT / "scripts" / "run_curator.py")]
    if args.curator_max_network_enrich is not None:
        curator_command.extend(["--max-network-enrich", str(args.curator_max_network_enrich)])

    commands = []
    if not args.skip_collect_news:
        commands.append(
            {
                "name": "collect_news",
                "command": collect_news,
                "artifacts": {"step1_raw_articles": str(RUNTIME_PIPELINE_ROOT / "step1_raw_articles.json")},
            }
        )
    commands.extend(
        [
            {
                "name": "collect_youtube",
                "command": collect_youtube,
                "artifacts": {"step1_raw_youtube": str(RUNTIME_PIPELINE_ROOT / "step1_raw_youtube.json")},
            },
            {
                "name": "dedup_filter",
                "command": [python, str(PUBLIC_SITE_ROOT / "scripts" / "dedup_filter.py")],
                "artifacts": {"step2_filtered": str(RUNTIME_PIPELINE_ROOT / "step2_filtered.json")},
            },
            {
                "name": "content_curator",
                "command": curator_command,
                "artifacts": {
                    "step3_classified": str(RUNTIME_PIPELINE_ROOT / "step3_classified.json"),
                    "step4_selected": str(RUNTIME_PIPELINE_ROOT / "step4_selected.json"),
                    "step5_summarized": str(RUNTIME_PIPELINE_ROOT / "step5_summarized.json"),
                },
            },
            {
                "name": "publish_db",
                "command": [python, str(PUBLIC_SITE_ROOT / "scripts" / "db_writer.py")],
                "artifacts": {"articles_db": str(RUNTIME_DB_ROOT / "articles.db")},
            },
            {
                "name": "publish_web",
                "command": [python, str(PUBLIC_SITE_ROOT / "scripts" / "web_updater.py")],
                "artifacts": {"web_index": str(PUBLIC_SITE_ROOT / "web" / "index.html")},
            },
        ]
    )
    if not args.skip_outbound_notifications:
        commands.extend(
            [
                {
                    "name": "publish_telegram",
                    "command": [python, str(PUBLIC_SITE_ROOT / "scripts" / "telegram_bot.py")],
                    "artifacts": {},
                },
                {
                    "name": "publish_slack",
                    "command": [python, str(PUBLIC_SITE_ROOT / "scripts" / "slack_bot.py")],
                    "artifacts": {},
                },
            ]
        )

    try:
        for entry in commands:
            update_step(status_path, entry["name"], "running", artifacts=entry["artifacts"])
            stdout = run_step(entry["command"])
            update_step(
                status_path,
                entry["name"],
                "completed",
                details={"stdout": stdout},
                artifacts=entry["artifacts"],
            )
    except subprocess.CalledProcessError as error:
        update_step(
            status_path,
            entry["name"],
            "failed",
            details={"returncode": error.returncode, "stderr": (error.stderr or "").strip()},
            artifacts=entry["artifacts"],
        )
        complete_run(status_path, success=False, error=(error.stderr or str(error)).strip())
        raise
    finally:
        release_lock(lock_path)

    complete_run(status_path, success=True)
    run_step([python, str(PUBLIC_SITE_ROOT / "scripts" / "web_updater.py")])
    print("pipeline=completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
