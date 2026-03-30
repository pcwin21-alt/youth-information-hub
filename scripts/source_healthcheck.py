from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.collect import (
    apply_source_filters,
    fetch_url,
    load_source_config,
    parse_feed,
    parse_korea_withyou_policy_news,
    parse_opm_press_release,
)
from youth_info_platform.io_utils import write_json


def inspect_source(source: dict) -> dict:
    try:
        payload = fetch_url(source["url"])
        parser = source.get("parser", "rss")
        if parser == "rss":
            items = parse_feed(payload, source["name"], source.get("kind", "news"))
        elif parser == "opm_press_release":
            items = parse_opm_press_release(payload, source["url"], source["name"], source.get("kind", "news"))
        elif parser == "korea_withyou_policy_news":
            items = parse_korea_withyou_policy_news(payload, source["url"], source["name"], source.get("kind", "news"))
        else:
            return {
                "name": source["name"],
                "status": "unsupported_parser",
                "total_items": 0,
                "filtered_items": 0,
                "sample_titles": [],
            }
        filtered = apply_source_filters(items, source)
        return {
            "name": source["name"],
            "status": "ok",
            "total_items": len(items),
            "filtered_items": len(filtered),
            "sample_titles": [item["title"] for item in filtered[:3]],
        }
    except Exception as error:
        return {
            "name": source["name"],
            "status": f"error:{error.__class__.__name__}",
            "total_items": 0,
            "filtered_items": 0,
            "sample_titles": [],
        }


def main() -> int:
    config_path = ROOT / ".claude" / "skills" / "collect-news" / "source_config.yaml"
    sources = load_source_config(str(config_path))
    report: list[dict] = []
    for source in sources:
        if not source.get("enabled", False):
            print(f'- {source["name"]}: disabled')
            report.append(
                {
                    "name": source["name"],
                    "status": "disabled",
                    "total_items": 0,
                    "filtered_items": 0,
                    "sample_titles": [],
                }
            )
            continue
        entry = inspect_source(source)
        report.append(entry)
        print(
            f'- {entry["name"]}: {entry["status"]} / '
            f'total_items={entry["total_items"]} / filtered_items={entry["filtered_items"]}'
        )
    output_path = ROOT / "output" / "source_healthcheck.json"
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
