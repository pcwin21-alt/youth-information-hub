from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import PUBLIC_WEB_ROOT, RUNTIME_PIPELINE_ROOT
from youth_info_platform.date_audit import build_article_date_audit_report, write_article_date_audit_report


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def require_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing_required_file:{path}")


def count_marker(path: Path, marker: str) -> int:
    return path.read_text(encoding="utf-8-sig").count(marker)


def article_list_from_payload(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", default=str(RUNTIME_PIPELINE_ROOT / "pipeline_status.json"))
    parser.add_argument("--classified-file", default=str(RUNTIME_PIPELINE_ROOT / "step3_classified.json"))
    parser.add_argument("--selected-file", default=str(RUNTIME_PIPELINE_ROOT / "step4_selected.json"))
    parser.add_argument("--summarized-file", default=str(RUNTIME_PIPELINE_ROOT / "step5_summarized.json"))
    parser.add_argument("--funnel-file", default=str(RUNTIME_PIPELINE_ROOT / "article_funnel.json"))
    parser.add_argument("--ops-radar-file", default=str(RUNTIME_PIPELINE_ROOT / "ops_radar.json"))
    parser.add_argument("--date-audit-file", default=str(RUNTIME_PIPELINE_ROOT / "article_date_audit.json"))
    parser.add_argument("--web-root", default=str(PUBLIC_WEB_ROOT))
    parser.add_argument("--min-articles", type=int, default=1)
    parser.add_argument("--min-news-cards", type=int, default=0)
    args = parser.parse_args()

    status_file = Path(args.status_file)
    classified_file = Path(args.classified_file)
    selected_file = Path(args.selected_file)
    summarized_file = Path(args.summarized_file)
    funnel_file = Path(args.funnel_file)
    ops_radar_file = Path(args.ops_radar_file)
    date_audit_file = Path(args.date_audit_file)
    web_root = Path(args.web_root)

    require_file(status_file)
    require_file(classified_file)
    require_file(selected_file)
    require_file(summarized_file)
    require_file(funnel_file)
    # Prebuilt Pages deploys also depend on the checked-in ops radar artifact.
    require_file(ops_radar_file)
    require_file(web_root / "index.html")
    require_file(web_root / "news.html")
    require_file(web_root / "policies.html")
    require_file(web_root / "hub.html")
    require_file(web_root / "tools.html")
    require_file(web_root / "contact.html")

    status = load_json(status_file)
    classified = load_json(classified_file)
    selected = load_json(selected_file)
    summarized = load_json(summarized_file)
    funnel = load_json(funnel_file)
    ops_radar = load_json(ops_radar_file)

    if not isinstance(status, dict):
        raise SystemExit("invalid_status_payload")
    if status.get("state") != "completed":
        raise SystemExit(f"pipeline_not_completed:{status.get('state')}")
    if status.get("error"):
        raise SystemExit(f"pipeline_error:{status.get('error')}")
    if not isinstance(summarized, list):
        raise SystemExit("invalid_summarized_payload")
    if not isinstance(ops_radar, dict):
        raise SystemExit("invalid_ops_radar_payload")
    if not isinstance(ops_radar.get("items"), list):
        raise SystemExit("invalid_ops_radar_items")
    if not isinstance(classified, list):
        raise SystemExit("invalid_classified_payload")
    if not isinstance(selected, list):
        raise SystemExit("invalid_selected_payload")
    if not isinstance(funnel, list):
        raise SystemExit("invalid_funnel_payload")
    if len(summarized) < args.min_articles:
        raise SystemExit(
            f"insufficient_articles:min_required={args.min_articles} actual={len(summarized)}"
        )

    date_audit = build_article_date_audit_report(
        {
            "step3_classified.json": article_list_from_payload(classified),
            "step4_selected.json": article_list_from_payload(selected),
            "step5_summarized.json": article_list_from_payload(summarized),
            "article_funnel.json": article_list_from_payload(funnel),
            "ops_radar.json": article_list_from_payload(ops_radar),
        }
    )
    write_article_date_audit_report(date_audit_file, date_audit)
    if date_audit["error_count"]:
        raise SystemExit(
            f"date_audit_failed:errors={date_audit['error_count']} report={date_audit_file}"
        )

    news_cards = count_marker(web_root / "news.html", 'data-article-card="true"')
    if news_cards < args.min_news_cards:
        raise SystemExit(
            f"insufficient_news_cards:min_required={args.min_news_cards} actual={news_cards}"
        )

    print(f"verified_pipeline_state={status.get('state')}")
    print(f"verified_article_count={len(summarized)}")
    print(f"verified_ops_radar_count={len(ops_radar.get('items', []))}")
    print(f"verified_date_audit_errors={date_audit['error_count']}")
    print(f"verified_date_audit_warnings={date_audit['warning_count']}")
    print(f"verified_date_audit_report={date_audit_file}")
    print(f"verified_news_cards={news_cards}")
    print(f"verified_web_root={web_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
