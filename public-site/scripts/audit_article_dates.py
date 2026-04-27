from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import RUNTIME_PIPELINE_ROOT

from youth_info_platform.date_audit import build_article_date_audit_report, write_article_date_audit_report
from youth_info_platform.io_utils import read_json


def _load_article_list(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, default=[])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Article JSON path to audit. Can be provided multiple times.",
    )
    parser.add_argument("--output", default=str(RUNTIME_PIPELINE_ROOT / "article_date_audit.json"))
    parser.add_argument("--no-warnings", action="store_true")
    parser.add_argument("--no-fail", action="store_true")
    args = parser.parse_args()

    input_paths = [Path(value) for value in args.input] or [
        RUNTIME_PIPELINE_ROOT / "step3_classified.json",
        RUNTIME_PIPELINE_ROOT / "step5_summarized.json",
        RUNTIME_PIPELINE_ROOT / "article_funnel.json",
        RUNTIME_PIPELINE_ROOT / "ops_radar.json",
    ]
    article_groups = {
        path.name: _load_article_list(path)
        for path in input_paths
        if path.exists()
    }
    report = build_article_date_audit_report(article_groups, include_warnings=not args.no_warnings)
    output_path = Path(args.output)
    write_article_date_audit_report(output_path, report)

    print(f"date_audit_report={output_path}")
    print(f"date_audit_articles={report['article_count']}")
    print(f"date_audit_errors={report['error_count']}")
    print(f"date_audit_warnings={report['warning_count']}")
    if report["error_count"] and not args.no_fail:
        raise SystemExit(f"date_audit_failed:errors={report['error_count']} report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
