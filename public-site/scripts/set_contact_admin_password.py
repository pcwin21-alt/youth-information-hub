from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from _bootstrap import ensure_shared_src

from youth_info_platform.contact_config import ADMIN_SETTINGS_PATH, write_admin_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", help="Password to write without prompting")
    parser.add_argument("--path", default=str(ADMIN_SETTINGS_PATH))
    args = parser.parse_args()

    password = args.password or getpass.getpass("새 관리자 비밀번호: ")
    if len(password) < 8:
        raise SystemExit("password_too_short")

    path = write_admin_settings(password, Path(args.path))
    print(f"admin_settings_path={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
