from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PUBLIC_CONTENT_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.io_utils import read_json, write_json
from youth_info_platform.public_archive import build_public_archive_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge public classified articles into the static archive.")
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step3_classified.json"))
    parser.add_argument("--output", default=str(PUBLIC_CONTENT_ROOT / "public_article_archive.json"))
    parser.add_argument("--retention-days", type=int, default=365)
    parser.add_argument("--research-retention-days", type=int, default=3650)
    args = parser.parse_args()

    incoming = read_json(Path(args.input), default=[])
    if not isinstance(incoming, list):
        raise SystemExit("classified input must be a JSON array")
    output_path = Path(args.output)
    existing = read_json(output_path, default={})
    if not isinstance(existing, dict):
        existing = {}
    payload = build_public_archive_payload(
        existing,
        incoming,
        retention_days=max(args.retention_days, 1),
        research_retention_days=max(args.research_retention_days, 1),
    )
    write_json(output_path, payload)
    print(f"public_archive={output_path} articles={payload['article_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
