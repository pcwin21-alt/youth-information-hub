from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.collect import collect_articles, load_source_config
from youth_info_platform.io_utils import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / ".claude" / "skills" / "collect-news" / "source_config.yaml"))
    parser.add_argument("--output", default=str(ROOT / "output" / "step1_raw_articles.json"))
    parser.add_argument("--use-sample-data", action="store_true")
    parser.add_argument("--fallback-to-sample", action="store_true")
    args = parser.parse_args()

    sources = load_source_config(args.config)
    articles = collect_articles(
        sources,
        use_sample_data=args.use_sample_data,
        fallback_to_sample=args.fallback_to_sample,
    )
    write_json(Path(args.output), articles)
    print(f"collected_articles={len(articles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
