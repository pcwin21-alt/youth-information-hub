from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.curation import deduplicate_and_filter
from youth_info_platform.io_utils import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "output" / "step1_raw_articles.json"))
    parser.add_argument("--output", default=str(ROOT / "output" / "step2_filtered.json"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    filtered = deduplicate_and_filter(articles)
    write_json(Path(args.output), filtered)
    print(f"filtered_articles={len(filtered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
