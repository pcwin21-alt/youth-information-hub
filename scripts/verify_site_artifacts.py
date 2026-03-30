from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def require_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing_required_file:{path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", default=str(ROOT / "output" / "pipeline_status.json"))
    parser.add_argument("--summarized-file", default=str(ROOT / "output" / "step5_summarized.json"))
    parser.add_argument("--web-root", default=str(ROOT / "web"))
    parser.add_argument("--min-articles", type=int, default=1)
    args = parser.parse_args()

    status_file = Path(args.status_file)
    summarized_file = Path(args.summarized_file)
    web_root = Path(args.web_root)

    require_file(status_file)
    require_file(summarized_file)
    require_file(web_root / "index.html")
    require_file(web_root / "news.html")
    require_file(web_root / "policies.html")
    require_file(web_root / "hub.html")
    require_file(web_root / "tools.html")
    require_file(web_root / "contact.html")

    status = load_json(status_file)
    summarized = load_json(summarized_file)

    if not isinstance(status, dict):
        raise SystemExit("invalid_status_payload")
    if status.get("state") != "completed":
        raise SystemExit(f"pipeline_not_completed:{status.get('state')}")
    if status.get("error"):
        raise SystemExit(f"pipeline_error:{status.get('error')}")
    if not isinstance(summarized, list):
        raise SystemExit("invalid_summarized_payload")
    if len(summarized) < args.min_articles:
        raise SystemExit(
            f"insufficient_articles:min_required={args.min_articles} actual={len(summarized)}"
        )

    print(f"verified_pipeline_state={status.get('state')}")
    print(f"verified_article_count={len(summarized)}")
    print(f"verified_web_root={web_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
