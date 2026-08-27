from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import RUNTIME_PIPELINE_ROOT

from youth_info_platform.collect import collect_videos_with_status
from youth_info_platform.io_utils import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(RUNTIME_PIPELINE_ROOT / "step1_raw_youtube.json"))
    parser.add_argument("--status-output", default=str(RUNTIME_PIPELINE_ROOT / "youtube_collection_status.json"))
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config" / "youtube_sources.json"))
    parser.add_argument("--use-sample-data", action="store_true")
    args = parser.parse_args()

    videos, status = collect_videos_with_status(
        use_sample_data=args.use_sample_data,
        config_path=args.config,
    )
    write_json(Path(args.output), videos)
    write_json(Path(args.status_output), status)
    print(f"collected_videos={len(videos)} state={status['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
