from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.io_utils import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "output" / "step1_naver_news.json"))
    args = parser.parse_args()
    write_json(Path(args.output), [])
    print("naver_news_crawler=not_configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
