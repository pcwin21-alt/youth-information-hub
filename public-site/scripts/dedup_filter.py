from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import RUNTIME_PIPELINE_ROOT

from youth_info_platform.curation import deduplicate_and_filter
from youth_info_platform.io_utils import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step1_raw_articles.json"))
    parser.add_argument("--output", default=str(RUNTIME_PIPELINE_ROOT / "step2_filtered.json"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    filtered = deduplicate_and_filter(articles)
    write_json(Path(args.output), filtered)
    print(f"filtered_articles={len(filtered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
