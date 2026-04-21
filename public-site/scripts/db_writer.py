from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import RUNTIME_DB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.io_utils import read_json
from youth_info_platform.publish_utils import upsert_articles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step5_summarized.json"))
    parser.add_argument("--db", default=str(RUNTIME_DB_ROOT / "articles.db"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    count = upsert_articles(Path(args.db), articles)
    print(f"db_upserted={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
