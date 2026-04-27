from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .article_metadata import article_identity_key, is_google_news_url
from .io_utils import write_json


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _article_url_candidates(article: dict[str, Any]) -> list[str]:
    values = [
        article.get("url"),
        article.get("canonical_url"),
        article.get("publisher_url"),
        article.get("feed_url"),
    ]
    return [str(value).strip() for value in values if str(value or "").strip()]


def _has_google_news_url(article: dict[str, Any]) -> bool:
    return any(is_google_news_url(value) for value in _article_url_candidates(article))


def _has_resolved_publisher_url(article: dict[str, Any]) -> bool:
    for key in ("publisher_url", "canonical_url"):
        value = str(article.get(key) or "").strip()
        if value and not is_google_news_url(value):
            return True
    return False


def is_unresolved_google_news_article(article: dict[str, Any]) -> bool:
    return _has_google_news_url(article) and not _has_resolved_publisher_url(article)


def _base_issue(article: dict[str, Any], *, context: str, code: str, severity: str) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "context": context,
        "article_key": article_identity_key(article),
        "title": article.get("title"),
        "url": article.get("url"),
        "canonical_url": article.get("canonical_url"),
        "publisher_url": article.get("publisher_url"),
        "feed_url": article.get("feed_url"),
        "source": article.get("source"),
        "source_name": article.get("source_name"),
        "published_date": article.get("published_date"),
        "publisher_published_at": article.get("publisher_published_at"),
        "portal_published_at": article.get("portal_published_at"),
    }


def audit_article_dates(
    articles: list[dict[str, Any]],
    *,
    context: str,
    include_warnings: bool = True,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        if not is_unresolved_google_news_article(article):
            continue

        if article.get("published_date") or article.get("publisher_published_at"):
            issues.append(
                _base_issue(
                    article,
                    context=context,
                    code="untrusted_google_news_published_date",
                    severity="error",
                )
            )
        elif include_warnings:
            issues.append(
                _base_issue(
                    article,
                    context=context,
                    code="unresolved_google_news_without_published_date",
                    severity="warning",
                )
            )
    return issues


def build_article_date_audit_report(
    article_groups: dict[str, list[dict[str, Any]]],
    *,
    include_warnings: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    article_count = 0
    for context, articles in article_groups.items():
        article_count += len(articles)
        issues.extend(audit_article_dates(articles, context=context, include_warnings=include_warnings))

    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    return {
        "generated_at": generated_at or _now_iso(),
        "article_count": article_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }


def write_article_date_audit_report(path: Path, report: dict[str, Any]) -> None:
    write_json(path, report)
