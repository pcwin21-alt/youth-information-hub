from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _bootstrap import PUBLIC_SITE_ROOT, PUBLIC_WEB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.io_utils import write_json, write_text
from youth_info_platform.pipeline_feedback import (
    DEFAULT_THRESHOLDS,
    build_feedback_report,
    build_metrics,
    render_markdown_report,
    should_fail,
)


def run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PUBLIC_SITE_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = (result.stdout or "").strip()
    if stdout:
        print(stdout)
    return stdout


def run_source_healthcheck() -> None:
    run_command([sys.executable, str(PUBLIC_SITE_ROOT / "scripts" / "source_healthcheck.py")])


def run_conservative_self_heal(*, with_source_healthcheck: bool) -> list[str]:
    actions: list[str] = []
    if with_source_healthcheck:
        run_source_healthcheck()
        actions.append("source_healthcheck")

    if not (RUNTIME_PIPELINE_ROOT / "article_date_audit.json").exists():
        run_command([sys.executable, str(PUBLIC_SITE_ROOT / "scripts" / "audit_article_dates.py")])
        actions.append("audit_article_dates")

    if not (PUBLIC_WEB_ROOT / "index.html").exists():
        run_command([sys.executable, str(PUBLIC_SITE_ROOT / "scripts" / "web_updater.py")])
        actions.append("web_updater")

    metrics = build_metrics(pipeline_root=RUNTIME_PIPELINE_ROOT, web_root=PUBLIC_WEB_ROOT)
    report = build_feedback_report(metrics)
    has_blocking_core_issue = any(
        item["severity"] == "critical"
        and item["code"]
        in {
            "missing_artifact",
            "low_raw_article_count",
            "low_filtered_article_count",
            "low_classified_article_count",
            "low_summarized_article_count",
            "pipeline_not_completed",
            "pipeline_status_error",
        }
        for item in report["findings"]
    )
    if has_blocking_core_issue:
        run_command(
            [
                sys.executable,
                str(PUBLIC_SITE_ROOT / "scripts" / "cron_runner.py"),
                "--skip-outbound-notifications",
                "--skip-feedback",
            ]
        )
        actions.append("cron_runner")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default=str(RUNTIME_PIPELINE_ROOT / "pipeline_feedback_report.json"))
    parser.add_argument("--output-md", default=str(RUNTIME_PIPELINE_ROOT / "pipeline_feedback_report.md"))
    parser.add_argument("--run-source-healthcheck", action="store_true")
    parser.add_argument("--self-heal", action="store_true")
    parser.add_argument("--fail-on", choices=["critical", "warning", "never"], default="critical")
    for key, value in DEFAULT_THRESHOLDS.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=int, default=value)
    args = parser.parse_args()

    threshold_overrides = {
        key: getattr(args, key)
        for key in DEFAULT_THRESHOLDS
        if getattr(args, key) != DEFAULT_THRESHOLDS[key]
    }

    healed_actions: list[str] = []
    if args.self_heal:
        healed_actions = run_conservative_self_heal(with_source_healthcheck=args.run_source_healthcheck)
    elif args.run_source_healthcheck:
        run_source_healthcheck()

    metrics = build_metrics(pipeline_root=RUNTIME_PIPELINE_ROOT, web_root=PUBLIC_WEB_ROOT)
    report = build_feedback_report(metrics, threshold_overrides)
    if healed_actions:
        report["self_heal_actions"] = healed_actions

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    write_json(output_json, report)
    write_text(output_md, render_markdown_report(report))

    print(f"pipeline_feedback_verdict={report['verdict']}")
    print(f"pipeline_feedback_findings={len(report['findings'])}")
    print(f"pipeline_feedback_report={output_json}")
    print(f"pipeline_feedback_markdown={output_md}")
    if healed_actions:
        print(f"pipeline_feedback_self_heal_actions={','.join(healed_actions)}")

    return 1 if should_fail(report, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
