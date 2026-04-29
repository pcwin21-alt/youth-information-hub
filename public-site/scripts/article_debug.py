from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import RUNTIME_PIPELINE_ROOT

from youth_info_platform.article_funnel import match_funnel_entries
from youth_info_platform.article_metadata import normalize_tracking_url, parse_generic_article_page
from youth_info_platform.collect import fetch_url
from youth_info_platform.io_utils import read_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--funnel-file", default=str(RUNTIME_PIPELINE_ROOT / "article_funnel.json"))
    parser.add_argument("--url", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if not args.url and not args.title:
        raise SystemExit("article_debug_requires_url_or_title")

    funnel = read_json(Path(args.funnel_file), default=[]) or []
    requested_url = args.url.strip()
    requested_title = args.title.strip()
    resolved_metadata: dict[str, object] | None = None
    resolution_error = ""

    query_url = requested_url
    query_title = requested_title

    if requested_url:
        try:
            html_text = fetch_url(requested_url, timeout=20)
            resolved_metadata = parse_generic_article_page(html_text, requested_url)
            query_url = (
                resolved_metadata.get("publisher_url")
                or resolved_metadata.get("canonical_url")
                or requested_url
            )
            if not query_title:
                query_title = str(resolved_metadata.get("title") or "")
        except Exception as exc:  # pragma: no cover - network fallback path
            resolution_error = str(exc)

    matches = match_funnel_entries(funnel, title=query_title, url=query_url, limit=args.limit)
    top_match = matches[0] if matches else None

    report = {
        "requested_url": requested_url or None,
        "requested_title": requested_title or None,
        "normalized_url": normalize_tracking_url(query_url) if query_url else None,
        "resolved_metadata": _compact_metadata(resolved_metadata),
        "resolution_error": resolution_error or None,
        "result": _result_label(top_match),
        "matches": matches,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _compact_metadata(metadata: dict[str, object] | None) -> dict[str, object] | None:
    if not metadata:
        return None
    return {
        "canonical_url": metadata.get("canonical_url"),
        "publisher_url": metadata.get("publisher_url"),
        "portal_urls": metadata.get("portal_urls"),
        "publisher_published_at": metadata.get("publisher_published_at"),
        "section": metadata.get("section"),
        "article_type": metadata.get("article_type"),
        "region": metadata.get("region"),
        "issue_tags": metadata.get("issue_tags"),
        "topic_tags": metadata.get("topic_tags"),
        "location_tags": metadata.get("location_tags"),
        "lead_text": metadata.get("lead_text"),
        "youth_excerpt": metadata.get("youth_excerpt"),
        "image_url": metadata.get("image_url"),
        "image_source": metadata.get("image_source"),
        "publisher_icon_url": metadata.get("publisher_icon_url"),
        "body_preview": str(metadata.get("body_text") or "")[:240],
    }


def _result_label(match: dict[str, object] | None) -> str:
    if not match:
        return "not_collected"
    flags = match.get("pipeline_flags") or {}
    if flags.get("published"):
        return "published"
    if flags.get("selected"):
        return "selected_not_published"
    if flags.get("classified"):
        return "classified_not_selected"
    if flags.get("deduped"):
        return "deduped_only"
    if flags.get("collected"):
        return "collected_only"
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
