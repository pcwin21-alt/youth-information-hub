from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PUBLIC_CONFIG_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.collect import collect_articles_with_manifest, load_source_config
from youth_info_platform.io_utils import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PUBLIC_CONFIG_ROOT / "source_config.yaml"))
    parser.add_argument("--output", default=str(RUNTIME_PIPELINE_ROOT / "step1_raw_articles.json"))
    parser.add_argument(
        "--manifest-output",
        default=str(RUNTIME_PIPELINE_ROOT / "source_collection_manifest.json"),
    )
    parser.add_argument("--use-sample-data", action="store_true")
    parser.add_argument("--fallback-to-sample", action="store_true")
    parser.add_argument(
        "--preserve-previous-on-empty",
        action="store_true",
        help="Keep the last successful collection instead of replacing it with an empty result.",
    )
    args = parser.parse_args()

    sources = load_source_config(args.config)
    articles, manifest = collect_articles_with_manifest(
        sources,
        use_sample_data=args.use_sample_data,
        fallback_to_sample=args.fallback_to_sample,
    )
    output_path = Path(args.output)
    write_json(Path(args.manifest_output), manifest)
    if args.preserve_previous_on_empty and not articles and output_path.exists():
        print(
            "collected_articles=0 preserved_previous=true "
            f"failed_sources={manifest['failed_sources']}"
        )
        return 0
    write_json(output_path, articles)
    print(
        f"collected_articles={len(articles)} "
        f"successful_sources={manifest['successful_sources']} "
        f"failed_sources={manifest['failed_sources']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
