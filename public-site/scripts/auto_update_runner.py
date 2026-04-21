from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from _bootstrap import PUBLIC_SITE_ROOT, REPO_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.auto_update_config import (
    load_auto_update_settings,
    load_auto_update_status,
    save_auto_update_status,
)
from youth_info_platform.io_utils import read_json


STEP1_RAW_ARTICLES_PATH = RUNTIME_PIPELINE_ROOT / "step1_raw_articles.json"


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def resolve_interval_minutes(settings: dict[str, Any], override: int | None) -> int:
    if override is not None:
        return override
    try:
        value = int(settings.get("interval_minutes", 10))
    except (TypeError, ValueError):
        value = 10
    return max(3, min(60, value))


def compute_articles_fingerprint(path: Path) -> tuple[str, int]:
    articles = read_json(path, default=[]) or []
    normalized = sorted(
        (
            str(article.get("url") or "").strip(),
            str(article.get("title") or "").strip(),
            str(article.get("source") or "").strip(),
            str(article.get("published_date") or "").strip(),
        )
        for article in articles
        if isinstance(article, dict)
    )
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest, len(normalized)


def update_status(**changes: Any) -> dict[str, Any]:
    current = load_auto_update_status()
    current_pid = current.get("runner_pid")
    started_at = current.get("started_at") if current_pid == os.getpid() else None
    started_at = started_at or now_iso()
    payload = {
        **current,
        **changes,
        "runner_pid": os.getpid(),
        "started_at": started_at,
        "updated_at": now_iso(),
    }
    return save_auto_update_status(payload)


def tail_lines(value: str, limit: int = 8) -> str:
    lines = [line for line in (value or "").splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


def run_command(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    record = {
        "command": Path(command[-1]).name,
        "args": command,
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    return record


def next_check_at(interval_minutes: int) -> str:
    return (datetime.now().astimezone() + timedelta(minutes=interval_minutes)).replace(microsecond=0).isoformat()


def sleep_loop(seconds: int) -> None:
    remaining = max(0, seconds)
    while remaining > 0:
        time.sleep(min(remaining, 5))
        remaining -= 5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-minutes", type=int)
    parser.add_argument("--use-sample-data", action="store_true")
    args = parser.parse_args()

    python = sys.executable
    rss_fetcher_command = [python, str(PUBLIC_SITE_ROOT / "scripts" / "rss_fetcher.py")]
    publish_command = [
        python,
        str(PUBLIC_SITE_ROOT / "scripts" / "cron_runner.py"),
        "--skip-collect-news",
        "--curator-max-network-enrich",
        "20",
    ]
    if args.use_sample_data:
        rss_fetcher_command.extend(["--use-sample-data", "--fallback-to-sample"])
        publish_command.append("--use-sample-data")

    update_status(state="starting", last_error="", current_action="runner_boot")

    cycles = 0
    try:
        while True:
            settings = load_auto_update_settings()
            interval_minutes = resolve_interval_minutes(settings, args.interval_minutes)
            status_enabled = bool(settings.get("enabled"))
            settings_snapshot = {
                "enabled": status_enabled,
                "interval_minutes": interval_minutes,
                "skip_outbound_notifications": bool(settings.get("skip_outbound_notifications", True)),
                "publish_on_article_change_only": bool(settings.get("publish_on_article_change_only", True)),
            }

            if not status_enabled:
                update_status(
                    state="disabled",
                    current_action="waiting_for_enable",
                    settings=settings_snapshot,
                    next_check_at=next_check_at(1),
                )
                if args.once:
                    return 0
                sleep_loop(60)
                continue

            try:
                update_status(
                    state="checking",
                    current_action="collect_news_probe",
                    settings=settings_snapshot,
                    last_checked_at=now_iso(),
                )
                probe_record = run_command(rss_fetcher_command)
                fingerprint, article_count = compute_articles_fingerprint(STEP1_RAW_ARTICLES_PATH)
                current_status = load_auto_update_status()
                last_published_fingerprint = current_status.get("last_published_fingerprint") or ""
                should_publish = fingerprint != last_published_fingerprint
                if not settings_snapshot["publish_on_article_change_only"]:
                    should_publish = True

                update_status(
                    state="checked",
                    current_action="probe_complete",
                    settings=settings_snapshot,
                    last_checked_at=now_iso(),
                    last_probe_result=tail_lines(probe_record["stdout"]),
                    last_seen_fingerprint=fingerprint,
                    last_seen_article_count=article_count,
                )

                if not should_publish:
                    update_status(
                        state="idle_no_change",
                        current_action="sleeping",
                        settings=settings_snapshot,
                        next_check_at=next_check_at(interval_minutes),
                    )
                    cycles += 1
                    if args.once:
                        return 0
                    sleep_loop(interval_minutes * 60)
                    continue

                publish_command_run = list(publish_command)
                if settings_snapshot["skip_outbound_notifications"]:
                    publish_command_run.append("--skip-outbound-notifications")

                update_status(
                    state="publishing",
                    current_action="run_pipeline",
                    settings=settings_snapshot,
                    last_change_detected_at=now_iso(),
                    last_candidate_count=article_count,
                )
                publish_record = run_command(publish_command_run)
                update_status(
                    state="published",
                    current_action="sleeping",
                    settings=settings_snapshot,
                    last_published_at=now_iso(),
                    last_publish_result=tail_lines(publish_record["stdout"]),
                    last_published_fingerprint=fingerprint,
                    last_published_article_count=article_count,
                    last_error="",
                    next_check_at=next_check_at(interval_minutes),
                )
                cycles += 1
                if args.once:
                    return 0
                sleep_loop(interval_minutes * 60)
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or exc.output or str(exc)).strip()
                state = "error"
                if "pipeline_locked:" in stderr:
                    state = "waiting_for_lock"
                update_status(
                    state=state,
                    current_action="sleeping",
                    settings=settings_snapshot,
                    last_error=stderr[:2000],
                    next_check_at=next_check_at(interval_minutes),
                )
                if args.once:
                    return 1
                sleep_loop(interval_minutes * 60)
                continue
    except KeyboardInterrupt:
        update_status(state="stopped", current_action="interrupted")
        return 0
    except Exception as exc:  # noqa: BLE001
        update_status(
            state="error",
            current_action="stopped",
            last_error=str(exc)[:2000],
            settings=load_auto_update_settings(),
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
