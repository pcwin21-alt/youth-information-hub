from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from youth_info_platform.article_metadata import (
    article_identity_key,
    normalize_tracking_url,
    preferred_article_url,
    resolve_article_metadata,
)
from youth_info_platform.curation import classify_articles
from youth_info_platform.editorial import (
    DECISION_DEFAULT,
    DECISION_EXCLUDE,
    DECISION_INCLUDE,
    apply_clean_signal,
    build_article_identifiers,
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


def build_synced_article_defaults(article: dict[str, Any], *, is_manual_entry: bool) -> dict[str, Any]:
    normalized = apply_clean_signal(dict(article))
    published_raw = normalized.get("published_date")
    published_date = parse_datetime(published_raw) if isinstance(published_raw, str) else None
    return {
        "title": (normalized.get("title") or "").strip(),
        "article_url": preferred_article_url(normalized).strip(),
        "source_name": (
            normalized.get("source")
            or normalized.get("source_name")
            or normalized.get("publisher_domain")
            or ""
        ).strip(),
        "source_url": (
            normalized.get("source_homepage_url")
            or normalized.get("source_url")
            or normalized.get("publisher_url")
            or normalized.get("canonical_url")
            or ""
        ),
        "source_kind": (normalized.get("source_kind") or "").strip(),
        "published_date": published_date,
        "region": (normalized.get("region") or "").strip(),
        "categories": list(normalized.get("categories") or []),
        "governance_scope": (normalized.get("governance_scope") or "").strip(),
        "hub_owner_label": (normalized.get("hub_owner_label") or "").strip(),
        "hub_topics": list(normalized.get("hub_topics") or []),
        "importance_score": normalized.get("importance_score"),
        "selection_bucket": (normalized.get("selection_bucket") or "").strip(),
        "is_noise": bool(normalized.get("is_noise")),
        "is_official_source": bool(normalized.get("is_official_source")),
        "is_manual_entry": bool(is_manual_entry),
        "clean_score": int(normalized.get("clean_score") or 0),
        "clean_labels": list(normalized.get("clean_labels") or []),
        "lead_text": (normalized.get("lead_text") or "").strip(),
        "summary": (normalized.get("summary") or "").strip(),
        "raw_payload": normalized,
    }


def collect_override_identifiers(article: SyncedArticle) -> list[str]:
    payload = dict(article.raw_payload or {})
    payload.setdefault("article_key", article.article_key)
    payload.setdefault("url", article.article_url)
    payload.setdefault("title", article.title)
    payload.setdefault("published_date", article.published_date.isoformat() if article.published_date else None)
    payload.setdefault("source", article.source_name)
    payload.setdefault("source_name", article.source_name)
    return build_article_identifiers(payload)


def build_manual_article_payload(article: SyncedArticle) -> dict[str, Any]:
    payload = dict(article.raw_payload or {})
    payload.update(
        {
            "article_key": article.article_key,
            "title": article.title,
            "url": payload.get("url") or article.article_url,
            "publisher_url": payload.get("publisher_url") or article.article_url,
            "canonical_url": payload.get("canonical_url") or article.article_url,
            "source": article.source_name or payload.get("source") or payload.get("source_name") or "",
            "source_name": article.source_name or payload.get("source_name") or payload.get("source") or "",
            "source_url": article.source_url or payload.get("source_url") or payload.get("source_homepage_url") or "",
            "source_kind": article.source_kind or payload.get("source_kind") or "news",
            "published_date": article.published_date.isoformat() if article.published_date else payload.get("published_date"),
            "region": article.region,
            "categories": list(article.categories or []),
            "governance_scope": article.governance_scope,
            "hub_owner_label": article.hub_owner_label,
            "hub_topics": list(article.hub_topics or []),
            "importance_score": article.importance_score,
            "selection_bucket": article.selection_bucket,
            "is_noise": article.is_noise,
            "is_official_source": article.is_official_source,
            "lead_text": article.lead_text,
            "summary": article.summary,
            "editorial_decision": article.editorial_decision,
            "editorial_is_highlighted": article.editorial_is_highlighted,
            "editorial_note": article.editorial_note,
            "editorial_updated_at": article.editorial_updated_at.isoformat() if article.editorial_updated_at else None,
            "editorial_updated_by": article.editorial_updated_by.username if article.editorial_updated_by else "",
            "is_manual_entry": True,
            "clean_score": article.clean_score,
            "clean_labels": list(article.clean_labels or []),
            "is_clean_article": article.is_clean_article,
            "pipeline_flags": {
                **(payload.get("pipeline_flags") or {}),
                "collected": True,
                "deduped": True,
                "classified": True,
                "selected": False,
                "published": False,
            },
        }
    )
    return apply_clean_signal(payload)


def build_editorial_overrides_payload() -> dict[str, Any]:
    article_records = []
    manual_records = []

    articles = SyncedArticle.objects.exclude(
        editorial_decision=DECISION_DEFAULT,
        editorial_is_highlighted=False,
    ).order_by("-editorial_is_highlighted", "editorial_decision", "-editorial_updated_at")
    for article in articles:
        article_records.append(
            {
                "article_key": article.article_key,
                "title": article.title,
                "article_url": article.article_url or preferred_article_url(article.raw_payload or {}),
                "decision": article.editorial_decision,
                "is_highlighted": bool(article.editorial_is_highlighted),
                "note": article.editorial_note,
                "updated_at": article.editorial_updated_at.isoformat() if article.editorial_updated_at else None,
                "updated_by": article.editorial_updated_by.username if article.editorial_updated_by else "",
                "identifiers": collect_override_identifiers(article),
            }
        )

    manual_articles = SyncedArticle.objects.filter(is_manual_entry=True).order_by("-published_date", "-updated_at")
    for article in manual_articles:
        manual_records.append(build_manual_article_payload(article))

    return {
        "generated_at": None,
        "source": "institution-site",
        "articles": article_records,
        "manual_articles": manual_records,
    }


def export_editorial_overrides() -> str:
    payload = build_editorial_overrides_payload()
    path = editorial_overrides_path()
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


def _candidate_source_name(article: dict[str, Any], *, fallback_url: str) -> str:
    for candidate in (
        article.get("source_name"),
        article.get("source"),
        article.get("publisher_domain"),
        urlparse(fallback_url).netloc.lower(),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def build_manual_article_candidate(raw_url: str) -> dict[str, Any]:
    normalized_url = normalize_tracking_url(raw_url)
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_article_url")

    seed = {
        "url": normalized_url,
        "title": "",
        "source": parsed.netloc.lower(),
        "source_name": parsed.netloc.lower(),
        "source_kind": "news",
        "source_url": f"{parsed.scheme}://{parsed.netloc}/",
        "published_date": None,
        "lead_text": "",
    }
    resolved = resolve_article_metadata(seed, homepage_cache={}, page_cache={})
    title = str(resolved.get("title") or "").strip()
    if not title:
        raise ValueError("unresolved_article_title")

    resolved["source"] = _candidate_source_name(resolved, fallback_url=normalized_url)
    resolved["source_name"] = _candidate_source_name(resolved, fallback_url=normalized_url)
    if not resolved.get("source_url") and resolved.get("publisher_domain"):
        resolved["source_url"] = f'https://{resolved["publisher_domain"]}'

    classified = classify_articles([resolved])[0]
    classified["editorial_decision"] = DECISION_INCLUDE
    classified["editorial_is_highlighted"] = False
    classified["editorial_note"] = (classified.get("editorial_note") or "").strip()
    classified["is_manual_entry"] = True
    classified["pipeline_flags"] = {
        **classified.get("pipeline_flags", {}),
        "collected": True,
        "deduped": True,
        "classified": True,
        "selected": False,
        "published": False,
    }
    return apply_clean_signal(classified)


def find_existing_synced_article(article: dict[str, Any]) -> SyncedArticle | None:
    article_key = article_identity_key(article)
    candidate_identifiers = set(build_article_identifiers(article))
    if article_key:
        existing = SyncedArticle.objects.filter(article_key=article_key).first()
        if existing is not None:
            return existing

    for existing in SyncedArticle.objects.all():
        if candidate_identifiers.intersection(collect_override_identifiers(existing)):
            return existing
    return None


def create_manual_synced_article(raw_url: str, actor: AbstractBaseUser) -> tuple[SyncedArticle, bool]:
    candidate = build_manual_article_candidate(raw_url)
    existing = find_existing_synced_article(candidate)
    if existing is not None:
        return existing, False

    article_key = article_identity_key(candidate)
    defaults = build_synced_article_defaults(candidate, is_manual_entry=True)
    article = SyncedArticle.objects.create(
        article_key=article_key,
        editorial_decision=DECISION_INCLUDE,
        editorial_is_highlighted=False,
        editorial_note="",
        editorial_updated_at=timezone.now(),
        editorial_updated_by=actor,
        **defaults,
    )
    return article, True


__all__ = [
    "DECISION_DEFAULT",
    "DECISION_EXCLUDE",
    "DECISION_INCLUDE",
    "PipelineLockedError",
    "build_manual_article_candidate",
    "build_synced_article_defaults",
    "collect_override_identifiers",
    "create_admin_audit_log",
    "create_manual_synced_article",
    "export_editorial_overrides",
    "find_existing_synced_article",
    "load_pipeline_lock_snapshot",
    "run_contact_settings_refresh",
    "run_manual_news_refresh",
    "run_public_editorial_refresh",
    "user_can_manage_editorial",
]
