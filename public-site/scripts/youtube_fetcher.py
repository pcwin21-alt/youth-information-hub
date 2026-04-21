from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import RUNTIME_PIPELINE_ROOT

from youth_info_platform.collect import collect_videos
from youth_info_platform.io_utils import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(RUNTIME_PIPELINE_ROOT / "step1_raw_youtube.json"))
    parser.add_argument("--use-sample-data", action="store_true")
    args = parser.parse_args()

    videos = collect_videos(use_sample_data=args.use_sample_data)
    write_json(Path(args.output), videos)
    print(f"collected_videos={len(videos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
