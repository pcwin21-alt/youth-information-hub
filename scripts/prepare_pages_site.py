from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def normalize_cname(value: str | None) -> str | None:
    if not value:
        return None
    cname = value.strip()
    return cname or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-root", default=str(ROOT / "web"))
    parser.add_argument("--site-dir", default=str(ROOT / "dist"))
    parser.add_argument("--status-file", default=str(ROOT / "output" / "pipeline_status.json"))
    parser.add_argument("--selected-file", default=str(ROOT / "output" / "step4_selected.json"))
    parser.add_argument("--summarized-file", default=str(ROOT / "output" / "step5_summarized.json"))
    parser.add_argument("--cname", default=os.environ.get("PAGES_CNAME", ""))
    args = parser.parse_args()

    web_root = Path(args.web_root)
    site_dir = Path(args.site_dir)
    site_data_dir = site_dir / "site-data"

    if not web_root.exists():
        raise SystemExit(f"web_root_missing:{web_root}")

    if site_dir.exists():
        shutil.rmtree(site_dir)
    shutil.copytree(web_root, site_dir)

    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    copy_if_exists(Path(args.status_file), site_data_dir / "pipeline_status.json")
    copy_if_exists(Path(args.selected_file), site_data_dir / "selected.json")
    copy_if_exists(Path(args.summarized_file), site_data_dir / "summarized.json")

    cname = normalize_cname(args.cname)
    if cname:
        (site_dir / "CNAME").write_text(f"{cname}\n", encoding="utf-8")

    print(f"pages_site={site_dir}")
    print(f"pages_site_data={site_data_dir}")
    if cname:
        print(f"pages_cname={cname}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
