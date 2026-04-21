from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import RUNTIME_PIPELINE_ROOT

from youth_info_platform.article_funnel import build_article_funnel
from youth_info_platform.article_metadata import enrich_articles_for_curation
from youth_info_platform.curation import classify_articles, select_articles, summarize_articles
from youth_info_platform.editorial import apply_editorial_overrides
from youth_info_platform.io_utils import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step2_filtered.json"))
    parser.add_argument("--classified-output", default=str(RUNTIME_PIPELINE_ROOT / "step3_classified.json"))
    parser.add_argument("--selected-output", default=str(RUNTIME_PIPELINE_ROOT / "step4_selected.json"))
    parser.add_argument("--summarized-output", default=str(RUNTIME_PIPELINE_ROOT / "step5_summarized.json"))
    parser.add_argument("--funnel-output", default=str(RUNTIME_PIPELINE_ROOT / "article_funnel.json"))
    parser.add_argument("--max-network-enrich", type=int, default=240)
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    enriched = enrich_articles_for_curation(articles, max_network_enrich=args.max_network_enrich)
    classified = classify_articles(enriched)
    classified = apply_editorial_overrides(classified)
    selected, classified_with_selection = select_articles(classified)
    summarized = summarize_articles(selected)
    funnel = build_article_funnel(enriched, classified_with_selection, selected, summarized)

    write_json(Path(args.classified_output), classified_with_selection)
    write_json(Path(args.selected_output), selected)
    write_json(Path(args.summarized_output), summarized)
    write_json(Path(args.funnel_output), funnel)
    print(
        f"enriched={len(enriched)} classified={len(classified_with_selection)} "
        f"selected={len(selected)} summarized={len(summarized)} funnel={len(funnel)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
