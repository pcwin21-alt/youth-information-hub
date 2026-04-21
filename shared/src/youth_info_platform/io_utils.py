from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def shared_root() -> Path:
    return project_root() / "shared"


def public_site_root() -> Path:
    return project_root() / "public-site"


def institution_site_root() -> Path:
    return project_root() / "institution-site"


def runtime_root() -> Path:
    return project_root() / "runtime"


def runtime_pipeline_root() -> Path:
    return runtime_root() / "pipeline"


def runtime_db_root() -> Path:
    return runtime_root() / "db"


def runtime_logs_root() -> Path:
    return runtime_root() / "logs"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")
