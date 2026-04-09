from __future__ import annotations

from datetime import datetime
from typing import Any

from .article_metadata import (
    article_identity_key,
    normalize_article_record,
    normalize_article_title,
    normalize_tracking_url,
    preferred_article_url,
    title_similarity,
)


def build_article_funnel(
    collected_articles: list[dict[str, Any]],
    classified_articles: list[dict[str, Any]],
    selected_articles: list[dict[str, Any]],
    summarized_articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}

    def merge(article: dict[str, Any], *, stage: str) -> None:
        normalized = normalize_article_record(article)
        key = article_identity_key(normalized)
        entry = entries.setdefault(key, _base_entry(normalized, key))

        entry["title"] = normalized.get("title") or entry.get("title")
        entry["feed_url"] = normalized.get("feed_url") or entry.get("feed_url")
        entry["canonical_url"] = normalized.get("canonical_url") or entry.get("canonical_url")
        entry["publisher_url"] = normalized.get("publisher_url") or entry.get("publisher_url")
        entry["portal_urls"] = list(
            dict.fromkeys((entry.get("portal_urls") or []) + (normalized.get("portal_urls") or []))
        )
        entry["preferred_url"] = preferred_article_url(normalized) or entry.get("preferred_url")
        entry["source"] = normalized.get("source") or entry.get("source")
        entry["source_name"] = normalized.get("source_name") or entry.get("source_name")
        entry["source_kind"] = normalized.get("source_kind") or entry.get("source_kind")
        entry["publisher_domain"] = normalized.get("publisher_domain") or entry.get("publisher_domain")
        entry["publisher_published_at"] = normalized.get("publisher_published_at") or entry.get("publisher_published_at")
        entry["portal_published_at"] = normalized.get("portal_published_at") or entry.get("portal_published_at")
        entry["published_date"] = normalized.get("published_date") or entry.get("published_date")
        entry["resolved_at"] = normalized.get("resolved_at") or entry.get("resolved_at")
        entry["section"] = normalized.get("section") or entry.get("section")
        entry["article_type"] = normalized.get("article_type") or entry.get("article_type")
        entry["authors"] = list(dict.fromkeys((entry.get("authors") or []) + (normalized.get("authors") or [])))
        entry["categories"] = normalized.get("categories") or entry.get("categories") or []
        entry["region"] = normalized.get("region") or entry.get("region")
        entry["issue_tags"] = list(dict.fromkeys((entry.get("issue_tags") or []) + (normalized.get("issue_tags") or [])))
        entry["location_tags"] = list(
            dict.fromkeys((entry.get("location_tags") or []) + (normalized.get("location_tags") or []))
        )
        entry["governance_scope"] = normalized.get("governance_scope") or entry.get("governance_scope")
        entry["governance_activity_types"] = normalized.get("governance_activity_types") or entry.get(
            "governance_activity_types"
        ) or []
        entry["hub_topics"] = normalized.get("hub_topics") or entry.get("hub_topics") or []
        entry["importance_score"] = normalized.get("importance_score", entry.get("importance_score"))
        entry["selection_bucket"] = normalized.get("selection_bucket") or entry.get("selection_bucket")
        entry["selection_reason"] = normalized.get("selection_reason") or entry.get("selection_reason")
        entry["classification_reason"] = normalized.get("classification_reason") or entry.get("classification_reason")
        entry["drop_reason"] = normalized.get("drop_reason") or entry.get("drop_reason")
        entry["summary"] = normalized.get("summary") or entry.get("summary")
        entry["display_badges"] = normalized.get("display_badges") or entry.get("display_badges") or []
        entry["matched_urls"] = sorted(
            {
                normalize_tracking_url(url)
                for url in [
                    entry.get("feed_url"),
                    entry.get("canonical_url"),
                    entry.get("publisher_url"),
                    *(entry.get("portal_urls") or []),
                    normalized.get("url"),
                ]
                if url
            }
        )
        entry["pipeline_flags"] = {
            **entry.get("pipeline_flags", {}),
            **normalized.get("pipeline_flags", {}),
            stage: True,
        }
        if stage == "collected":
            entry["collected_count"] = int(entry.get("collected_count", 0)) + 1

    for article in collected_articles:
        merge(article, stage="collected")
        merge(article, stage="deduped")
    for article in classified_articles:
        merge(article, stage="classified")
    for article in selected_articles:
        merge(article, stage="selected")
    for article in summarized_articles:
        merge(article, stage="published")

    return sorted(entries.values(), key=_funnel_sort_key, reverse=True)


def match_funnel_entries(
    funnel: list[dict[str, Any]],
    *,
    title: str | None = None,
    url: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    normalized_url = normalize_tracking_url(url) if url else ""
    normalized_title = normalize_article_title(title)
    scored: list[tuple[float, dict[str, Any]]] = []

    for entry in funnel:
        score = 0.0
        if normalized_url and normalized_url in set(entry.get("matched_urls") or []):
            score = max(score, 1.0)
        elif normalized_url:
            preferred = normalize_tracking_url(entry.get("preferred_url") or "")
            if preferred and preferred == normalized_url:
                score = max(score, 1.0)

        if normalized_title:
            score = max(score, title_similarity(normalized_title, entry.get("title", "")))

        if score >= 0.82:
            scored.append((score, entry))

    scored.sort(key=lambda item: (item[0], _sort_timestamp(item[1])), reverse=True)
    return [entry for _, entry in scored[:limit]]


def _base_entry(article: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        "article_key": key,
        "title": article.get("title"),
        "feed_url": article.get("feed_url"),
        "canonical_url": article.get("canonical_url"),
        "publisher_url": article.get("publisher_url"),
        "portal_urls": list(article.get("portal_urls") or []),
        "preferred_url": preferred_article_url(article),
        "source": article.get("source"),
        "source_name": article.get("source_name"),
        "source_kind": article.get("source_kind"),
        "publisher_domain": article.get("publisher_domain"),
        "publisher_published_at": article.get("publisher_published_at"),
        "portal_published_at": article.get("portal_published_at"),
        "published_date": article.get("published_date"),
        "resolved_at": article.get("resolved_at"),
        "section": article.get("section"),
        "article_type": article.get("article_type"),
        "authors": list(article.get("authors") or []),
        "categories": list(article.get("categories") or []),
        "region": article.get("region"),
        "issue_tags": list(article.get("issue_tags") or []),
        "location_tags": list(article.get("location_tags") or []),
        "governance_scope": article.get("governance_scope"),
        "governance_activity_types": list(article.get("governance_activity_types") or []),
        "hub_topics": list(article.get("hub_topics") or []),
        "importance_score": article.get("importance_score"),
        "selection_bucket": article.get("selection_bucket"),
        "selection_reason": article.get("selection_reason"),
        "classification_reason": article.get("classification_reason"),
        "drop_reason": article.get("drop_reason"),
        "summary": article.get("summary"),
        "display_badges": list(article.get("display_badges") or []),
        "pipeline_flags": {
            "collected": False,
            "deduped": False,
            "classified": False,
            "selected": False,
            "published": False,
            "resolved_url": bool(article.get("pipeline_flags", {}).get("resolved_url")),
            "body_enriched": bool(article.get("pipeline_flags", {}).get("body_enriched")),
        },
        "matched_urls": [],
        "collected_count": 0,
    }


def _sort_timestamp(entry: dict[str, Any]) -> float:
    for value in (
        entry.get("publisher_published_at"),
        entry.get("published_date"),
        entry.get("portal_published_at"),
        entry.get("resolved_at"),
    ):
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
    return 0.0


def _funnel_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(entry.get("pipeline_flags", {}).get("published")),
        bool(entry.get("pipeline_flags", {}).get("selected")),
        bool(entry.get("pipeline_flags", {}).get("classified")),
        _sort_timestamp(entry),
        int(entry.get("importance_score") or 0),
    )
