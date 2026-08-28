from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from _bootstrap import PUBLIC_CONTENT_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.io_utils import read_json, write_json
from youth_info_platform.public_archive import (
    build_public_archive_payload,
    legacy_db_article_to_public_candidate,
)


def load_legacy_db_candidates(path: Path) -> list[dict]:
    if not path.exists():
        return []
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT url, title, source, published_date, region, categories, summary,
                   importance_score, is_official_source
            FROM articles
            ORDER BY published_date DESC, created_at DESC
            """
        ).fetchall()
    finally:
        connection.close()
    return [candidate for row in rows if (candidate := legacy_db_article_to_public_candidate(dict(row)))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge public classified articles into the static archive.")
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step3_classified.json"))
    parser.add_argument("--output", default=str(PUBLIC_CONTENT_ROOT / "public_article_archive.json"))
    parser.add_argument("--retention-days", type=int, default=365)
    parser.add_argument("--research-retention-days", type=int, default=3650)
    parser.add_argument(
        "--legacy-db",
        type=Path,
        help="One-time conservative backfill from the local articles SQLite table.",
    )
    args = parser.parse_args()

    incoming = read_json(Path(args.input), default=[])
    if not isinstance(incoming, list):
        raise SystemExit("classified input must be a JSON array")
    legacy_candidates = load_legacy_db_candidates(args.legacy_db) if args.legacy_db else []
    output_path = Path(args.output)
    existing = read_json(output_path, default={})
    if not isinstance(existing, dict):
        existing = {}
    if args.legacy_db:
        # A backfill can be rerun safely: candidates added by a preceding
        # backfill lack the modern classifier score, so replace that subset
        # rather than retaining records that no longer pass tighter rules.
        existing = dict(existing)
        existing["articles"] = [
            article
            for article in existing.get("articles", [])
            if isinstance(article, dict) and article.get("public_relevance_score") is not None
        ]
    payload = build_public_archive_payload(
        existing,
        [*incoming, *legacy_candidates],
        retention_days=max(args.retention_days, 1),
        research_retention_days=max(args.research_retention_days, 1),
    )
    write_json(output_path, payload)
    print(
        f"public_archive={output_path} articles={payload['article_count']} "
        f"incoming={len(incoming)} legacy_candidates={len(legacy_candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
