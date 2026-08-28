from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from youth_info_platform.article_metadata import article_identity_key, normalize_published_datetime
from youth_info_platform.curation import is_public_interest_article


SEOUL = timezone(timedelta(hours=9))
PUBLIC_ARCHIVE_SCHEMA_VERSION = 1
DEFAULT_RETENTION_DAYS = 365
DEFAULT_RESEARCH_RETENTION_DAYS = 10 * 365
LEGACY_MIN_IMPORTANCE_SCORE = 55
LEGACY_PLACEHOLDER_SOURCES = frozenset({"새 창 열림", "출처 미상", "미상"})
LEGACY_POLITICAL_KEYWORDS = (
    "선거",
    "후보",
    "출사표",
    "공약",
    "표심",
    "여당",
    "야당",
    "정당",
    "대선",
    "지방선거",
)

# Static Pages needs content sufficient for cards, filters, and detail pages.
# Do not retain raw response metadata, tracking payloads, or unlimited body text.
PUBLIC_ARTICLE_FIELDS = (
    "url",
    "canonical_url",
    "publisher_url",
    "feed_url",
    "portal_urls",
    "title",
    "source",
    "source_name",
    "source_kind",
    "publisher_domain",
    "publisher_icon_url",
    "image_url",
    "published_date",
    "publisher_published_at",
    "portal_published_at",
    "region",
    "categories",
    "topic_tags",
    "issue_tags",
    "display_badges",
    "article_type",
    "content_direction",
    "governance_scope",
    "governance_activity_types",
    "hub_topics",
    "authority",
    "ministry",
    "local_government",
    "official_source_name",
    "lead_text",
    "summary",
    "youth_excerpt",
    "body_text",
    "author",
    "is_official_source",
    "is_public_interest_article",
    "is_hub_candidate",
    "editorial_decision",
    "editorial_is_highlighted",
    "selection_bucket",
    "importance_score",
    "public_relevance_score",
    "related_article_count",
    "related_sources",
    "campaign_political",
    "substantive_promise",
    "campaign_attack",
    "weak_youth_signal",
    "missing_youth_content_signal",
)


def article_published_at(article: dict[str, Any]) -> str | None:
    for field in ("publisher_published_at", "published_date", "portal_published_at"):
        if normalized := normalize_published_datetime(article.get(field)):
            return normalized
    return None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SEOUL)
    return parsed.astimezone(SEOUL)


def is_public_archive_article(article: dict[str, Any]) -> bool:
    decision = str(article.get("editorial_decision") or "").strip().lower()
    if decision == "exclude":
        return False
    if article.get("editorial_is_highlighted") or decision == "include":
        return True
    return is_public_interest_article(article)


def legacy_db_article_to_public_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a pre-archive SQLite row only when it meets current public rules.

    Historical rows do not carry the full modern classifier payload. This bridge
    excludes synthetic URLs, placeholder publishers, undated records, and
    lower-confidence candidates before running the public-interest rule again.
    """

    url = str(row.get("url") or "").strip()
    title = str(row.get("title") or "").strip()
    source = str(row.get("source") or "").strip()
    published_date = normalize_published_datetime(row.get("published_date"))
    try:
        importance_score = int(row.get("importance_score") or 0)
    except (TypeError, ValueError):
        importance_score = 0

    if (
        not url.startswith(("https://", "http://"))
        or url.startswith("https://example.org/")
        or not title
        or not source
        or source in LEGACY_PLACEHOLDER_SOURCES
        or not published_date
        or importance_score < LEGACY_MIN_IMPORTANCE_SCORE
    ):
        return None

    categories = [
        value.strip()
        for value in str(row.get("categories") or "").replace("·", ",").split(",")
        if value.strip()
    ]
    is_official_source = bool(row.get("is_official_source"))
    summary = str(row.get("summary") or "").strip()
    legacy_text = f"{title} {summary}"
    if any(keyword in legacy_text for keyword in LEGACY_POLITICAL_KEYWORDS):
        return None
    candidate = {
        "url": url,
        "title": title,
        "source": source,
        "source_name": source,
        "source_kind": "official" if is_official_source else "news",
        "published_date": published_date,
        "publisher_published_at": published_date,
        "region": str(row.get("region") or "").strip(),
        "categories": categories,
        "topic_tags": categories[:3],
        "lead_text": summary,
        "summary": summary,
        "importance_score": importance_score,
        "is_official_source": is_official_source,
    }
    if not is_public_interest_article(candidate):
        return None
    candidate["is_public_interest_article"] = True
    return candidate


def compact_public_article(article: dict[str, Any]) -> dict[str, Any]:
    compact = {
        field: article[field]
        for field in PUBLIC_ARTICLE_FIELDS
        if field in article and article[field] not in (None, "", [], {})
    }
    compact["archive_key"] = article_identity_key(article)
    # The incoming record already passed the public-exposure predicate. Store
    # that decision because the compact archive intentionally omits raw parser
    # signals that would otherwise be needed to calculate it again.
    compact["is_public_interest_article"] = True
    if published_at := article_published_at(article):
        compact["published_at"] = published_at
        compact.setdefault("published_date", published_at)
    if body_text := compact.get("body_text"):
        compact["body_text"] = str(body_text)[:5000]
    return compact


def merge_article(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for field, value in incoming.items():
        if value not in (None, "", [], {}):
            merged[field] = value
    merged["archive_key"] = incoming.get("archive_key") or existing.get("archive_key")
    return merged


def merge_public_archive(
    existing_articles: list[dict[str, Any]],
    incoming_articles: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    research_retention_days: int = DEFAULT_RESEARCH_RETENTION_DAYS,
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for raw_article in existing_articles:
        if not isinstance(raw_article, dict):
            continue
        key = str(raw_article.get("archive_key") or article_identity_key(raw_article)).strip()
        if key:
            by_key[key] = compact_public_article(raw_article)

    for raw_article in incoming_articles:
        if not isinstance(raw_article, dict) or not is_public_archive_article(raw_article):
            continue
        compact = compact_public_article(raw_article)
        key = compact["archive_key"]
        by_key[key] = merge_article(by_key.get(key, {}), compact)

    reference = now.astimezone(SEOUL) if now else datetime.now(SEOUL)
    retained: list[dict[str, Any]] = []
    for article in by_key.values():
        published = parse_datetime(article_published_at(article) or article.get("published_at"))
        if published is None:
            continue
        is_research = str(article.get("source_kind") or "").strip().lower() == "research" or str(
            article.get("article_type") or ""
        ).strip().lower() in {"research", "paper", "report", "thesis"}
        days = research_retention_days if is_research else retention_days
        if published >= reference - timedelta(days=days):
            retained.append(article)
    return sorted(
        retained,
        key=lambda article: (
            parse_datetime(article_published_at(article) or article.get("published_at")) or datetime.min.replace(tzinfo=SEOUL),
            str(article.get("title") or ""),
        ),
        reverse=True,
    )


def build_public_archive_payload(
    existing_payload: dict[str, Any] | None,
    incoming_articles: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    research_retention_days: int = DEFAULT_RESEARCH_RETENTION_DAYS,
) -> dict[str, Any]:
    existing = (existing_payload or {}).get("articles", [])
    if not isinstance(existing, list):
        existing = []
    generated_at = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    articles = merge_public_archive(
        existing,
        incoming_articles,
        now=generated_at,
        retention_days=retention_days,
        research_retention_days=research_retention_days,
    )
    return {
        "schema_version": PUBLIC_ARCHIVE_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "retention_days": retention_days,
        "research_retention_days": research_retention_days,
        "article_count": len(articles),
        "articles": articles,
    }
