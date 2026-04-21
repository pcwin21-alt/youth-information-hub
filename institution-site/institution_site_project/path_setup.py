from __future__ import annotations

import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
SHARED_SRC = REPO_ROOT / "shared" / "src"
RUNTIME_ROOT = REPO_ROOT / "runtime"
RUNTIME_PIPELINE_ROOT = RUNTIME_ROOT / "pipeline"
RUNTIME_DB_ROOT = RUNTIME_ROOT / "db"
RUNTIME_LOGS_ROOT = RUNTIME_ROOT / "logs"


def configure_shared_imports() -> None:
    shared_src = str(SHARED_SRC)
    if shared_src not in sys.path:
        sys.path.insert(0, shared_src)
