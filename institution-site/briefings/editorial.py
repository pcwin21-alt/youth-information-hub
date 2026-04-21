from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from youth_info_platform.article_metadata import article_identity_key, normalize_tracking_url, preferred_article_url
from youth_info_platform.editorial import (
    DECISION_DEFAULT,
    DECISION_EXCLUDE,
    DECISION_FEATURE,
    editorial_overrides_path,
)
from youth_info_platform.io_utils import project_root, read_json, runtime_pipeline_root, write_json

from .models import AdminAuditLog, SyncedArticle


PIPELINE_LOCK_PATH = runtime_pipeline_root() / "pipeline.lock"


class PipelineLockedError(RuntimeError):
    def __init__(
        self,
        message: str = "pipeline_locked",
        *,
        lock_path: Path | None = None,
        lock_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.lock_path = lock_path
        self.lock_details = lock_details or {}


def user_can_manage_editorial(user: AbstractBaseUser | None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "staff_profile", None)
    return bool(profile and profile.role == profile.ROLE_PLATFORM_ADMIN)


def create_admin_audit_log(
    actor: AbstractBaseUser | None,
    scope: str,
    action: str,
    *,
    target_key: str = "",
    summary: str = "",
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
) -> AdminAuditLog:
    return AdminAuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        scope=scope,
        action=action,
        target_key=target_key[:300],
        summary=(summary or action)[:300],
        before_data=before_data or {},
        after_data=after_data or {},
    )


def collect_override_identifiers(article: SyncedArticle) -> list[str]:
    payload = dict(article.raw_payload or {})
    payload.setdefault("article_key", article.article_key)
    payload.setdefault("url", article.article_url)
    payload.setdefault("title", article.title)
    payload.setdefault("published_date", article.published_date.isoformat() if article.published_date else None)
    candidates = [
        article.article_key,
        article.article_url,
        payload.get("normalized_url"),
        payload.get("canonical_url"),
        payload.get("publisher_url"),
        payload.get("url"),
        payload.get("feed_url"),
        article_identity_key(payload),
    ]
    identifiers: list[str] = []
    for candidate in candidates:
        normalized = normalize_tracking_url(candidate)
        if normalized and normalized not in identifiers:
            identifiers.append(normalized)
    return identifiers


def build_editorial_overrides_payload() -> dict[str, Any]:
    articles = SyncedArticle.objects.exclude(editorial_decision=DECISION_DEFAULT).order_by(
        "editorial_decision",
        "editorial_feature_rank",
        "-editorial_updated_at",
    )
    records = []
    for article in articles:
        records.append(
            {
                "article_key": article.article_key,
                "title": article.title,
                "article_url": article.article_url or preferred_article_url(article.raw_payload or {}),
                "decision": article.editorial_decision,
                "feature_rank": article.editorial_feature_rank,
                "note": article.editorial_note,
                "updated_at": article.editorial_updated_at.isoformat() if article.editorial_updated_at else None,
                "updated_by": article.editorial_updated_by.username if article.editorial_updated_by else "",
                "identifiers": collect_override_identifiers(article),
            }
        )
    return {
        "generated_at": None,
        "source": "institution-site",
        "articles": records,
    }


def export_editorial_overrides() -> str:
    payload = build_editorial_overrides_payload()
    path = editorial_overrides_path()
    from django.utils import timezone

    payload["generated_at"] = timezone.now().isoformat()
    write_json(path, payload)
    return str(path)


def _run_repo_command(command: list[str]) -> dict[str, Any]:
    repo_root = project_root()
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    record = {
        "command": Path(command[-1]).name,
        "args": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    return record


def run_contact_settings_refresh() -> dict[str, Any]:
    repo_root = project_root()
    return _run_repo_command([sys.executable, str(repo_root / "public-site" / "scripts" / "web_updater.py")])


def run_public_editorial_refresh() -> list[dict[str, Any]]:
    repo_root = project_root()
    commands = [
        [sys.executable, str(repo_root / "public-site" / "scripts" / "run_curator.py")],
        [sys.executable, str(repo_root / "public-site" / "scripts" / "db_writer.py")],
        [sys.executable, str(repo_root / "public-site" / "scripts" / "web_updater.py")],
    ]
    return [_run_repo_command(command) for command in commands]


def load_pipeline_lock_snapshot() -> dict[str, Any]:
    try:
        payload = read_json(PIPELINE_LOCK_PATH, default={})
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "lock_path": str(PIPELINE_LOCK_PATH),
        "exists": PIPELINE_LOCK_PATH.exists(),
        "details": payload,
    }


def run_manual_news_refresh() -> list[dict[str, Any]]:
    if PIPELINE_LOCK_PATH.exists():
        snapshot = load_pipeline_lock_snapshot()
        raise PipelineLockedError(
            "pipeline_locked",
            lock_path=PIPELINE_LOCK_PATH,
            lock_details=snapshot,
        )

    repo_root = project_root()
    commands = [
        [sys.executable, str(repo_root / "public-site" / "scripts" / "rss_fetcher.py")],
        [sys.executable, str(repo_root / "public-site" / "scripts" / "dedup_filter.py")],
        [sys.executable, str(repo_root / "public-site" / "scripts" / "run_curator.py")],
        [sys.executable, str(repo_root / "public-site" / "scripts" / "db_writer.py")],
        [sys.executable, str(repo_root / "public-site" / "scripts" / "web_updater.py")],
    ]
    return [_run_repo_command(command) for command in commands]


__all__ = [
    "DECISION_DEFAULT",
    "DECISION_EXCLUDE",
    "DECISION_FEATURE",
    "create_admin_audit_log",
    "export_editorial_overrides",
    "load_pipeline_lock_snapshot",
    "PipelineLockedError",
    "run_contact_settings_refresh",
    "run_manual_news_refresh",
    "run_public_editorial_refresh",
    "user_can_manage_editorial",
]
