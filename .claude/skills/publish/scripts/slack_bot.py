from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print("slack_bot=skipped_no_credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

