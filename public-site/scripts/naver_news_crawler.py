from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PUBLIC_CONFIG_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.collect import collect_articles, load_source_config
from youth_info_platform.io_utils import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PUBLIC_CONFIG_ROOT / "source_config.yaml"))
    parser.add_argument("--output", default=str(RUNTIME_PIPELINE_ROOT / "step1_naver_news.json"))
    parser.add_argument("--use-sample-data", action="store_true")
    args = parser.parse_args()

    sources = [source for source in load_source_config(args.config) if source.get("parser") == "naver_news_search"]
    articles = collect_articles(sources, use_sample_data=args.use_sample_data, fallback_to_sample=False)
    write_json(Path(args.output), articles)
    print(f"naver_news_crawler={len(articles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
