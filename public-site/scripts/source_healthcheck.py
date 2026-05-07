from __future__ import annotations

from datetime import datetime
from _bootstrap import PUBLIC_CONFIG_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.collect import (
    apply_source_filters,
    fetch_source_items,
    load_source_config,
)
from youth_info_platform.date_audit import audit_article_dates
from youth_info_platform.io_utils import write_json


def inspect_source(source: dict) -> dict:
    base_entry = {
        "name": source["name"],
        "kind": source.get("kind"),
        "parser": source.get("parser"),
        "enabled": bool(source.get("enabled", False)),
        "source_channel": source.get("source_channel"),
        "region_id": source.get("region_id"),
        "region_name": source.get("region_name"),
    }
    try:
        items = fetch_source_items(source)
        filtered = apply_source_filters(items, source)
        date_issues = audit_article_dates(filtered, context=source["name"])
        return {
            **base_entry,
            "status": "ok",
            "total_items": len(items),
            "filtered_items": len(filtered),
            "date_error_count": sum(1 for issue in date_issues if issue.get("severity") == "error"),
            "date_warning_count": sum(1 for issue in date_issues if issue.get("severity") == "warning"),
            "date_issues": date_issues[:20],
            "sample_titles": [item["title"] for item in filtered[:3]],
        }
    except ValueError as error:
        if str(error).startswith("unsupported_parser:"):
            return {
                **base_entry,
                "status": "unsupported_parser",
                "total_items": 0,
                "filtered_items": 0,
                "date_error_count": 0,
                "date_warning_count": 0,
                "date_issues": [],
                "sample_titles": [],
            }
        raise
    except Exception as error:
        return {
            **base_entry,
            "status": f"error:{error.__class__.__name__}",
            "total_items": 0,
            "filtered_items": 0,
            "date_error_count": 0,
            "date_warning_count": 0,
            "date_issues": [],
            "sample_titles": [],
        }


def main() -> int:
    config_path = PUBLIC_CONFIG_ROOT / "source_config.yaml"
    sources = load_source_config(str(config_path))
    report: list[dict] = []
    for source in sources:
        if not source.get("enabled", False):
            print(f'- {source["name"]}: disabled')
            report.append(
                {
                    "name": source["name"],
                    "kind": source.get("kind"),
                    "parser": source.get("parser"),
                    "enabled": False,
                    "source_channel": source.get("source_channel"),
                    "region_id": source.get("region_id"),
                    "region_name": source.get("region_name"),
                    "status": "disabled",
                    "total_items": 0,
                    "filtered_items": 0,
                    "date_error_count": 0,
                    "date_warning_count": 0,
                    "date_issues": [],
                    "sample_titles": [],
                }
            )
            continue
        entry = inspect_source(source)
        report.append(entry)
        print(
            f'- {entry["name"]}: {entry["status"]} / '
            f'total_items={entry["total_items"]} / filtered_items={entry["filtered_items"]} / '
            f'date_errors={entry["date_error_count"]}'
        )
    output_path = RUNTIME_PIPELINE_ROOT / "source_healthcheck.json"
    write_json(
        output_path,
        {
            "generated_at": datetime.now().astimezone().isoformat(),
            "sources": report,
        },
    )
    print(f"healthcheck_report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
