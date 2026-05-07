from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _bootstrap import PUBLIC_SITE_ROOT, RUNTIME_DB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.status_utils import complete_run, initialize_status, update_step


SNAPSHOT_ARTIFACT_NAMES = ("step2_filtered.json", "step5_summarized.json", "pipeline_status.json")


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


def parse_status_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc).astimezone()
    return parsed.astimezone()


def safe_path_fragment(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value).strip("_")
    return cleaned[:80] or datetime.now(timezone.utc).astimezone().strftime("%H%M%S")


def archive_run_artifacts(status_path: Path) -> dict[str, object]:
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status = {}

    started_at = parse_status_time(status.get("started_at"))
    finished_at = parse_status_time(status.get("finished_at")) or datetime.now(timezone.utc).astimezone()
    run_id = safe_path_fragment(status.get("run_id") or finished_at.strftime("%H%M%S"))
    snapshot_dir = RUNTIME_PIPELINE_ROOT / "archive" / finished_at.date().isoformat() / run_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped_stale: list[str] = []
    for artifact_name in SNAPSHOT_ARTIFACT_NAMES:
        source_path = RUNTIME_PIPELINE_ROOT / artifact_name
        if not source_path.exists():
            continue

        if artifact_name != "pipeline_status.json" and started_at is not None:
            modified_at = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc).astimezone()
            if modified_at < started_at - timedelta(minutes=1):
                skipped_stale.append(artifact_name)
                continue

        shutil.copy2(source_path, snapshot_dir / artifact_name)
        copied.append(artifact_name)

    return {
        "snapshot_dir": str(snapshot_dir),
        "copied": copied,
        "skipped_stale": skipped_stale,
    }


def print_archive_snapshot(snapshot: dict[str, object]) -> None:
    copied = ",".join(snapshot.get("copied", [])) if snapshot.get("copied") else ""
    skipped_stale = ",".join(snapshot.get("skipped_stale", [])) if snapshot.get("skipped_stale") else ""
    print(f"archive_snapshot_dir={snapshot.get('snapshot_dir')}")
    print(f"archive_snapshot_files={copied}")
    if skipped_stale:
        print(f"archive_snapshot_skipped_stale={skipped_stale}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-sample-data", action="store_true")
    parser.add_argument("--skip-collect-news", action="store_true")
    parser.add_argument("--skip-outbound-notifications", action="store_true")
    parser.add_argument("--skip-feedback", action="store_true")
    parser.add_argument("--feedback-with-source-healthcheck", action="store_true")
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
                    "ops_radar": str(RUNTIME_PIPELINE_ROOT / "ops_radar.json"),
                },
            },
            {
                "name": "audit_article_dates",
                "command": [python, str(PUBLIC_SITE_ROOT / "scripts" / "audit_article_dates.py")],
                "artifacts": {"article_date_audit": str(RUNTIME_PIPELINE_ROOT / "article_date_audit.json")},
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
    if not args.skip_feedback:
        feedback_command = [
            python,
            str(PUBLIC_SITE_ROOT / "scripts" / "pipeline_feedback.py"),
            "--fail-on",
            "critical",
        ]
        if args.feedback_with_source_healthcheck:
            feedback_command.append("--run-source-healthcheck")
        commands.append(
            {
                "name": "pipeline_feedback",
                "command": feedback_command,
                "artifacts": {
                    "pipeline_feedback_report": str(RUNTIME_PIPELINE_ROOT / "pipeline_feedback_report.json"),
                    "pipeline_feedback_markdown": str(RUNTIME_PIPELINE_ROOT / "pipeline_feedback_report.md"),
                },
            }
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
        print_archive_snapshot(archive_run_artifacts(status_path))
        raise
    finally:
        release_lock(lock_path)

    complete_run(status_path, success=True)
    print_archive_snapshot(archive_run_artifacts(status_path))
    run_step([python, str(PUBLIC_SITE_ROOT / "scripts" / "web_updater.py")])
    print("pipeline=completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
