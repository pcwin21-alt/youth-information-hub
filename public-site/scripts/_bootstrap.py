from __future__ import annotations

import sys
from pathlib import Path


PUBLIC_SITE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PUBLIC_SITE_ROOT.parent
SHARED_SRC = REPO_ROOT / "shared" / "src"
RUNTIME_ROOT = REPO_ROOT / "runtime"
RUNTIME_PIPELINE_ROOT = RUNTIME_ROOT / "pipeline"
RUNTIME_DB_ROOT = RUNTIME_ROOT / "db"
RUNTIME_LOGS_ROOT = RUNTIME_ROOT / "logs"
PUBLIC_WEB_ROOT = PUBLIC_SITE_ROOT / "web"
PUBLIC_DIST_ROOT = PUBLIC_SITE_ROOT / "dist"
PUBLIC_CONFIG_ROOT = PUBLIC_SITE_ROOT / "config"
PUBLIC_CONTENT_ROOT = PUBLIC_SITE_ROOT / "content"
PUBLIC_DEPLOY_ROOT = PUBLIC_SITE_ROOT / "deploy"


def ensure_shared_src() -> None:
    shared_src = str(SHARED_SRC)
    if shared_src not in sys.path:
        sys.path.insert(0, shared_src)


ensure_shared_src()
