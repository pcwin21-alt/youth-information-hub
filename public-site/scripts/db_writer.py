from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import RUNTIME_DB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.io_utils import read_json
from youth_info_platform.publish_utils import upsert_article_archive, upsert_articles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step5_summarized.json"))
    parser.add_argument("--archive-input", default=str(RUNTIME_PIPELINE_ROOT / "step2_filtered.json"))
    parser.add_argument("--status-input", default=str(RUNTIME_PIPELINE_ROOT / "pipeline_status.json"))
    parser.add_argument("--db", default=str(RUNTIME_DB_ROOT / "articles.db"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    count = upsert_articles(Path(args.db), articles)
    archive_articles = read_json(Path(args.archive_input), default=[])
    status = read_json(Path(args.status_input), default={}) or {}
    archive_counts = upsert_article_archive(Path(args.db), archive_articles, run_id=status.get("run_id"))
    print(
        " ".join(
            [
                f"db_upserted={count}",
                f"archive_inserted={archive_counts['inserted']}",
                f"archive_updated={archive_counts['updated']}",
                f"archive_total={archive_counts['total']}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
