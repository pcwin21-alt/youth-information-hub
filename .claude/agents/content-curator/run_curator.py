from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.curation import classify_articles, select_articles, summarize_articles
from youth_info_platform.io_utils import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "output" / "step2_filtered.json"))
    parser.add_argument("--classified-output", default=str(ROOT / "output" / "step3_classified.json"))
    parser.add_argument("--selected-output", default=str(ROOT / "output" / "step4_selected.json"))
    parser.add_argument("--summarized-output", default=str(ROOT / "output" / "step5_summarized.json"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    classified = classify_articles(articles)
    selected = select_articles(classified)
    summarized = summarize_articles(selected)

    write_json(Path(args.classified_output), classified)
    write_json(Path(args.selected_output), selected)
    write_json(Path(args.summarized_output), summarized)
    print(f"classified={len(classified)} selected={len(selected)} summarized={len(summarized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
