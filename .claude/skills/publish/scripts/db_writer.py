from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.io_utils import read_json
from youth_info_platform.publish_utils import upsert_articles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "output" / "step5_summarized.json"))
    parser.add_argument("--db", default=str(ROOT / "db" / "articles.db"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    count = upsert_articles(Path(args.db), articles)
    print(f"db_upserted={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
