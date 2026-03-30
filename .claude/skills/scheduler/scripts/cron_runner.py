from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.status_utils import complete_run, initialize_status, update_step


def run_step(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
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
    args = parser.parse_args()

    python = sys.executable
    status_path = ROOT / "output" / "pipeline_status.json"
    lock_path = ROOT / "output" / "pipeline.lock"
    acquire_lock(lock_path)
    initialize_status(status_path)
    collect_news = [python, str(ROOT / ".claude" / "skills" / "collect-news" / "scripts" / "rss_fetcher.py")]
    collect_youtube = [python, str(ROOT / ".claude" / "skills" / "collect-youtube" / "scripts" / "youtube_fetcher.py")]
    if args.use_sample_data:
        collect_news.append("--use-sample-data")
        collect_news.append("--fallback-to-sample")
        collect_youtube.append("--use-sample-data")

    commands = [
        {
            "name": "collect_news",
            "command": collect_news,
            "artifacts": {"step1_raw_articles": str(ROOT / "output" / "step1_raw_articles.json")},
        },
        {
            "name": "collect_youtube",
            "command": collect_youtube,
            "artifacts": {"step1_raw_youtube": str(ROOT / "output" / "step1_raw_youtube.json")},
        },
        {
            "name": "dedup_filter",
            "command": [python, str(ROOT / ".claude" / "skills" / "dedup-filter" / "scripts" / "dedup_filter.py")],
            "artifacts": {"step2_filtered": str(ROOT / "output" / "step2_filtered.json")},
        },
        {
            "name": "content_curator",
            "command": [python, str(ROOT / ".claude" / "agents" / "content-curator" / "run_curator.py")],
            "artifacts": {
                "step3_classified": str(ROOT / "output" / "step3_classified.json"),
                "step4_selected": str(ROOT / "output" / "step4_selected.json"),
                "step5_summarized": str(ROOT / "output" / "step5_summarized.json"),
            },
        },
        {
            "name": "publish_db",
            "command": [python, str(ROOT / ".claude" / "skills" / "publish" / "scripts" / "db_writer.py")],
            "artifacts": {"articles_db": str(ROOT / "db" / "articles.db")},
        },
        {
            "name": "publish_web",
            "command": [python, str(ROOT / ".claude" / "skills" / "publish" / "scripts" / "web_updater.py")],
            "artifacts": {"web_index": str(ROOT / "web" / "index.html")},
        },
        {
            "name": "publish_telegram",
            "command": [python, str(ROOT / ".claude" / "skills" / "publish" / "scripts" / "telegram_bot.py")],
            "artifacts": {},
        },
        {
            "name": "publish_slack",
            "command": [python, str(ROOT / ".claude" / "skills" / "publish" / "scripts" / "slack_bot.py")],
            "artifacts": {},
        },
    ]

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
    run_step([python, str(ROOT / ".claude" / "skills" / "publish" / "scripts" / "web_updater.py")])
    print("pipeline=completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
